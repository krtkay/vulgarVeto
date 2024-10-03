import streamlit as st
import speech_recognition as sr
from gtts import gTTS
from pydub import AudioSegment
from tempfile import NamedTemporaryFile
import os
import io
import IPython.display as ipd

def transcribe_chunk(audio_chunk):
    recognizer = sr.Recognizer()
    with sr.AudioFile(audio_chunk) as source:
        audio_data = recognizer.record(source)
    try:
        text = recognizer.recognize_google(audio_data)
        return text
    except sr.UnknownValueError:
        return "Could not understand audio"
    except sr.RequestError as e:
        return "Could not request results; {0}".format(e)

def split_audio(audio_file, chunk_duration_ms):
    audio = AudioSegment.from_wav(audio_file)
    chunk_count = len(audio) // chunk_duration_ms + 1
    chunks = []
    for i in range(chunk_count):
        start_time = i * chunk_duration_ms
        end_time = (i + 1) * chunk_duration_ms
        if end_time > len(audio):
            end_time = len(audio)
        chunk = audio[start_time:end_time]
        with NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
            temp_filename = temp_file.name
            chunk.export(temp_filename, format="wav")
            chunks.append(temp_filename)
    return chunks

def transcribe_audio(audio_file, chunk_duration_ms):
    audio_chunks = split_audio(audio_file, chunk_duration_ms)
    transcriptions = []
    for chunk in audio_chunks:
        transcription = transcribe_chunk(chunk)
        transcriptions.append(transcription)

    full_text = ' '.join(transcriptions)
    return full_text

def filter_bad_words(text, bad_words, beep_sound):
    words = text.split()
    filtered_words = []
    for word in words:
        if word.lower() in bad_words:
            filtered_words.append(beep_sound)
        else:
            filtered_words.append(word)
    filtered_text = ' '.join(filtered_words)
    return filtered_text

# def text_to_speech(text, language='en'):
#     tts = gTTS(text=text, lang=language, slow=False)
#     with NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
#         temp_filename = temp_file.name
#         tts.save(temp_filename)
#         audio = AudioSegment.from_mp3(temp_filename)
#     return audio

def text_to_speech(text, language='en'):
    tts = gTTS(text=text, lang=language, slow=False)
    audio_file = io.BytesIO()
    tts.write_to_fp(audio_file)
    audio_file.seek(0)
    return audio_file

st.markdown(
    """
    <style>
    body {
        background-image: url("https://www.crazysocks.com/cdn/shop/articles/benefits-of-swearing_1600x.png?v=1688849137");
        background-attachment: fixed;
        background-size: cover;
    }
    </style>
    """,
    unsafe_allow_html=True
)

def main():
    bad_words_file_path = "en.txt"
    with open(bad_words_file_path, 'r') as file:
        bad_words = file.read().splitlines()
    beep_sound = "BEEP"

    st.title("VulgarVeto")

    # File upload section
    uploaded_file = st.file_uploader("Upload an audio file", type=["wav"])

    if uploaded_file:
        # Display the audio file
        st.audio(uploaded_file)

        transcription = ""
        if st.button("Filter Bad Words"):
            transcription = transcribe_audio(uploaded_file, 15000)
            st.write("Transcription:")
            st.write(transcription)
            filtered_text = filter_bad_words(transcription, bad_words, beep_sound)
            st.write("Filtered Transcription:")
            st.write(filtered_text)

            # Convert filtered text to speech
            filtered_audio = text_to_speech(filtered_text)
            st.audio(filtered_audio, format='audio/wav')

if __name__ == "__main__":
    main()