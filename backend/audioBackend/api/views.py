import librosa
import numpy as np
import soundfile as sf
import tensorflow as tf
from tensorflow import keras
from keras.models import model_from_json
from django.http import JsonResponse, FileResponse, HttpResponse
import os
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from wsgiref.util import FileWrapper

def noise_estimation(noisy_speech, n_fft, hop_length_fft):
#estimates the noise level of a noisy speech signal using spectral subtraction.
    stft_noisy_speech = librosa.stft(noisy_speech, n_fft=n_fft, hop_length=hop_length_fft)
    magnitude_noisy_speech = np.abs(stft_noisy_speech)
    smoothed_magnitude_noisy_speech = librosa.feature.mfcc(S=magnitude_noisy_speech, n_mfcc=12)
    noise_magnitude = np.min(smoothed_magnitude_noisy_speech, axis=0)
    return noise_magnitude, stft_noisy_speech


def audio_to_audio_frame_stack(audio,frame_length,frame_hop_length):
#audio array(numpy) is transformed to a matrix
    frame_stack_list=[]
    audio_length=audio.shape[0]
    for i in range(0,audio_length-frame_length+1,frame_hop_length):
        frame_stack_list.append(audio[i:i+frame_length])

    return np.vstack(frame_stack_list)


def audio_file_to_numpy(audio_path,sample_rate,frame_length, hop_length_frame,min_duration):
    y,sr=librosa.load(audio_path,sr=sample_rate)
    return np.vstack(audio_to_audio_frame_stack(y,frame_length,hop_length_frame))


def audio_to_magnitude_db_and_phase(n_fft,hop_length_fft,audio):
#stft on the audio matrix to calculate mag and phase
    stft_audio=librosa.stft(audio,n_fft=n_fft,hop_length=hop_length_fft)
    stft_audio_magnitude,stft_audio_phase=librosa.magphase(stft_audio)

    stft_audio_magnitude_db=librosa.amplitude_to_db(stft_audio_magnitude,ref=np.max)
    return stft_audio_magnitude_db,stft_audio_phase


def numpy_audio_to_matrix_spectrogram(numpy_audio, dim_square_spec, n_fft, hop_length_fft):
#audio ko sappai row ma stft laudai final euta matrix banauni
    dim=int(n_fft/2)+1
    tot_rows=numpy_audio.shape[0]
#     print(type(dim))
#     print(type(tot_rows))
    mag_matrix=np.zeros((tot_rows,dim,dim))
    phase_matrix=np.zeros((tot_rows,dim,dim),dtype=complex)
    for i in range (tot_rows):
        mag_matrix[i],phase_matrix[i]=audio_to_magnitude_db_and_phase(n_fft, hop_length_fft, numpy_audio[i])
    return mag_matrix,phase_matrix

def scaled_in(matrix_spec):
    "global scaling apply to noisy voice spectrograms (scale between -1 and 1)"
    matrix_spec = (matrix_spec + 46)/50
    return matrix_spec
def scaled_ou(matrix_spec):
    "global scaling apply to noise models spectrograms (scale between -1 and 1)"
    matrix_spec = (matrix_spec -6 )/82
    return matrix_spec

#Helper Functions
def magnitude_db_and_phase_to_audio(frame_length, hop_length_fft, stftaudio_magnitude_db, stftaudio_phase):
    """This functions reverts a spectrogram to an audio"""

    stftaudio_magnitude_rev = librosa.db_to_amplitude(stftaudio_magnitude_db, ref=1.0)

    # taking magnitude and phase of audio
    audio_reverse_stft = stftaudio_magnitude_rev * stftaudio_phase
    audio_reconstruct = librosa.core.istft(audio_reverse_stft, hop_length=hop_length_fft, length=frame_length)

    return audio_reconstruct


def matrix_spectrogram_to_numpy_audio(m_mag_db, m_phase, frame_length, hop_length_fft)  :
    #reverts the matrix spectrograms to numpy audio

    list_audio = []
    nb_spec = m_mag_db.shape[0]

    for i in range(nb_spec):
        audio_reconstruct = magnitude_db_and_phase_to_audio(frame_length, hop_length_fft, m_mag_db[i], m_phase[i])
        list_audio.append(audio_reconstruct)

    return np.vstack(list_audio)

def inv_scaled_ou(matrix_spec):
    #inverse global scaling apply to noise models spectrograms
    matrix_spec = matrix_spec * 82 + 6
    return matrix_spec

# @ensure_csrf_cookie
@csrf_exempt
def denoise_audio(request):
    if request.method == 'POST':
        #load JSON and create model
        weights_path = 'api/static'
        json_file = open(weights_path + '/model_unet.json', 'r')
        loaded_model_json = json_file.read()
        json_file.close()
        loaded_model = model_from_json(loaded_model_json)
        loaded_model.load_weights(weights_path + '/model_unet_best.h5')
        print("Model loaded from disk")

        #audio settings
        sample_rate=16000
        frame_length=16128
        hop_length_frame=16128
        hop_length_frame_noise=16128
        n_fft=511
        hop_length_fft=63
        audio_output_prediction = '_denoised.wav'
        dir_save_prediction = 'api/audio'

        #extract audio data from the request
        audio_data = request.FILES['audio_file']
        input_file_name = audio_data.name[0:-4]

        #perform denoising
        noisy_speech, _ = librosa.load(audio_data, sr=sample_rate)
        noise_magnitude, stft_noisy_speech = noise_estimation(noisy_speech, n_fft=511, hop_length_fft=hop_length_fft)
        enhanced_speech = np.copy(stft_noisy_speech)
        for i in range(enhanced_speech.shape[0]):
            enhanced_speech[i] = stft_noisy_speech[i] - noise_magnitude[i]
        enhanced_audio = librosa.istft(enhanced_speech, hop_length=hop_length_fft)

        sf.write(f"{dir_save_prediction}/{input_file_name}_spec{audio_output_prediction}", enhanced_audio, sample_rate, 'PCM_24')

        audio = np.vstack(audio_to_audio_frame_stack(enhanced_audio, frame_length, hop_length_frame))
        del enhanced_audio

        #Dimensions of squared spectrogram
        dim_square_spec = int(n_fft / 2) + 1
        print(dim_square_spec)

        # Create Amplitude and phase of the sounds
        m_amp_db_audio, m_pha_audio = numpy_audio_to_matrix_spectrogram(audio, dim_square_spec, n_fft, hop_length_fft)

        #global scaling to have distribution -1/1
        X_in = scaled_in(m_amp_db_audio)
        #Reshape for prediction
        X_in = X_in.reshape(X_in.shape[0], X_in.shape[1], X_in.shape[2], 1)
        #Prediction using loaded network
        X_pred = loaded_model.predict(X_in)
        #Rescale back the noise model
        inv_sca_X_pred = inv_scaled_ou(X_pred)
        #Remove noise model from noisy speech
        X_denoise = m_amp_db_audio - inv_sca_X_pred[:,:,:,0]
        #Reconstruct audio from denoised spectrogram and phase
        print(X_denoise.shape)
        print(m_pha_audio.shape)
        print(frame_length)
        print(hop_length_fft)
        audio_denoise_recons = matrix_spectrogram_to_numpy_audio(X_denoise, m_pha_audio, frame_length, hop_length_fft)
        #Number of frames
        nb_samples = audio_denoise_recons.shape[0]
        #Save all frames in one file
        denoise_long = (audio_denoise_recons.reshape(1, nb_samples * frame_length) * 20)
        # librosa.output.write_wav(dir_save_prediction + audio_output_prediction, denoise_long[0, :], 1000)
        sf.write(f"{dir_save_prediction}/{input_file_name}{audio_output_prediction}", denoise_long[0, :], sample_rate, 'PCM_24')

        # Return the denoised audio file as the response
        output_file_path = f"{dir_save_prediction}/{input_file_name}{audio_output_prediction}"
        if os.path.exists(output_file_path):
            try:
                #file in binary mode
                with open(output_file_path, 'rb') as file:
                    #a FileWrapper instance
                    wrapper = FileWrapper(file)
                    #an HttpResponse object with the FileWrapper as content
                    response = HttpResponse(wrapper, content_type='audio/wav')
                    response['Content-Disposition'] = 'attachment; filename='+input_file_name+audio_output_prediction

                    return response  #return the response

            except Exception as e:
                print(f"Error opening file: {e}")
                # Handle the exception appropriately
        else:
            return HttpResponse("File not found", status=404)  # Return a 404 response if the file does not exist

    else:
        return JsonResponse({'status': 'error', 'message': 'Method not allowed.'})
    