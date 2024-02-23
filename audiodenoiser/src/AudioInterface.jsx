import React, { useState, useRef } from "react";
import "./AudioInterface.css"; //CSS file

function AudioInterface() {
  const [audioFile, setAudioFile] = useState(null);
  const [outputAudio, setOutputAudio] = useState(null);
  const [inputKey, setInputKey] = useState(0); //inputKey state
  const inputAudioRef = useRef(null);
  const outputAudioRef = useRef(null);
  const [isPlayingInput, setIsPlayingInput] = useState(false);
  const [isPlayingOutput, setIsPlayingOutput] = useState(false);

  const handleFileChange = (event) => {
    const file = event.target.files[0];
    setAudioFile(file);
    setInputKey((prevKey) => prevKey + 1); //update inputKey to force re-render
  };

  const handleSubmitAudio = () => {
    if (!audioFile) return;
    //process the audio here
    //modelOutput = the output audio file
    //setOutputAudio(modelOutput);
  };

  const handlePlayPause = (audioRef) => {
    if (audioRef.current) {
      if (audioRef.current.paused) {
        audioRef.current.play();
        if (audioRef === inputAudioRef) {
          setIsPlayingInput(true);
        } else if (audioRef === outputAudioRef) {
          setIsPlayingOutput(true);
        }
      } else {
        audioRef.current.pause();
        if (audioRef === inputAudioRef) {
          setIsPlayingInput(false);
        } else if (audioRef === outputAudioRef) {
          setIsPlayingOutput(false);
        }
      }
    }
  };

  return (
    <div className="audio-interface-container">
      <div className="header-container">
        <h2 className="audio-denoiser-header">Audio Denoiser</h2>
        <p className="header-description">
        </p>
      </div>
      <input type="file" accept=".wav" onChange={handleFileChange} />
      {audioFile && (
        <div className="audio-player">
          <audio key={inputKey} ref={inputAudioRef} controls>
            <source src={URL.createObjectURL(audioFile)} type="audio/wav" />
            Your browser does not support the audio element.
          </audio>
          <div className="audio-control-container">
            <button onClick={() => handlePlayPause(inputAudioRef)}>
              {isPlayingInput ? "Pause" : "Play"}
            </button>
            <button
              className="submit-button"
              onClick={handleSubmitAudio}
              disabled={!audioFile}
            >
              Submit
            </button>
          </div>
        </div>
      )}
      {outputAudio && (
        <div className="audio-player">
          <audio ref={outputAudioRef} controls>
            <source src={URL.createObjectURL(outputAudio)} type="audio/wav" />
            Your browser does not support the audio element.
          </audio>
          <button onClick={() => handlePlayPause(outputAudioRef)}>
            {isPlayingOutput ? "Pause" : "Play"}
          </button>
        </div>
      )}
    </div>
  );
}

export default AudioInterface;
