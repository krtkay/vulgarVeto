# VulgarVeto

VulgarVeto is a Streamlit-based speech moderation application that transcribes uploaded audio files, detects offensive language using a curated profanity lexicon, and generates a cleaned audio playback with censored words replaced by placeholder beeps.

The system was designed to explore real-time speech moderation pipelines using Python-based speech recognition and text-to-speech technologies.

---

# Features

* Upload `.wav` audio files
* Automatic speech transcription using Google Speech Recognition
* Audio chunking for improved transcription accuracy
* Profanity filtering using a customizable bad-word lexicon
* Regenerated clean speech output using gTTS
* Streamlit-powered interactive UI
* Lightweight and beginner-friendly implementation

---

# Tech Stack

## Frontend

* Streamlit

## Speech Recognition

* SpeechRecognition
* Google Speech Recognition API

## Audio Processing

* PyDub

## Text-to-Speech

* gTTS (Google Text-to-Speech)

## Language

* Python

---

# Project Workflow

```text
Audio Upload
     ↓
Audio Chunking (15s windows)
     ↓
Speech-to-Text Transcription
     ↓
Profanity Detection
     ↓
Text Filtering
     ↓
Clean Audio Regeneration
     ↓
Filtered Playback
```

---

# Why Audio Chunking?

Long audio files often reduce transcription accuracy and may fail due to API limitations.

To improve reliability:

* audio is divided into 15-second chunks
* each chunk is transcribed independently
* all transcriptions are merged into a final output

This significantly improved transcription consistency and reduced recognition failures.

---

# Folder Structure

```text
VulgarVeto/
│
├── app.py
├── en.txt
├── requirements.txt
└── README.md
```

---

# Installation

## Clone Repository

```bash
git clone https://github.com/krtkay/VulgarVeto.git
cd VulgarVeto
```

---

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

# Requirements

Create a `requirements.txt` file containing:

```text
streamlit
SpeechRecognition
gTTS
pydub
ipython
```

---

# FFmpeg Requirement

PyDub requires FFmpeg to process audio files.

## Windows

1. Download FFmpeg:
   https://ffmpeg.org/download.html

2. Add FFmpeg `bin` folder to system PATH.

## Verify Installation

```bash
ffmpeg -version
```

---

# Run the Application

```bash
streamlit run app.py
```

---

# Usage

1. Launch the Streamlit application
2. Upload a `.wav` audio file
3. Click **Filter Bad Words**
4. View:

   * Original transcription
   * Filtered transcription
   * Clean generated audio

---

# Example

## Input

```text
This is some offensive speech example
```

## Output

```text
This is some BEEP speech example
```

---

# Current Limitations

* Supports only `.wav` files
* Uses Google Speech Recognition internet API
* Offensive-word matching is exact-word based
* Generated output replaces words textually rather than modifying original waveform audio

---

# Future Improvements

* Real-time microphone moderation
* Deep learning-based profanity detection
* Context-aware toxicity classification
* Direct waveform censorship instead of text regeneration
* Multi-language support
* Speaker diarization
* Faster streaming transcription using Whisper/Deepgram

---

# Performance

* Achieved approximately 90% transcription success on moderate-quality audio
* Improved recognition reliability using segmented chunk processing
* Generated filtered audio playback within seconds for short clips

---

# Learning Outcomes

This project helped explore:

* speech processing pipelines
* audio segmentation
* speech-to-text systems
* profanity filtering
* Streamlit application deployment
* text-to-speech synthesis

---

# Author

Kartikeya Bhatnagar

* GitHub: https://github.com/krtkay
* LinkedIn: https://linkedin.com/in/kartikeya-bhatnagar
