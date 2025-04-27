import streamlit as st
import speech_recognition as sr
from gtts import gTTS
from pydub import AudioSegment
from tempfile import NamedTemporaryFile
import io
import random
import time

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

def filter_bad_words(text, bad_words, censor_type):
    words = text.split()
    filtered_words = []
    
    beep_options = ["BEEP", "*bleep*", "$#@%!", "****", "[censored]", "[redacted]", "!@#$"]
    
    for word in words:
        word_lower = word.lower()
        # Check if the word contains a bad word
        if any(bad_word in word_lower for bad_word in bad_words):
            if censor_type == "Random":
                replacement = random.choice(beep_options)
            elif censor_type == "Dolphin":
                replacement = "🐬" * (len(word) // 2 + 1)
            elif censor_type == "Symbols":
                symbols = ["#", "@", "$", "%", "&", "*", "!"]
                replacement = ''.join(random.choice(symbols) for _ in range(len(word)))
            else:  # Default beep
                replacement = "BEEP"
            filtered_words.append(replacement)
        else:
            filtered_words.append(word)
            
    filtered_text = ' '.join(filtered_words)
    return filtered_text

def text_to_speech(text, language='en'):
    tts = gTTS(text=text, lang=language, slow=False)
    audio_file = io.BytesIO()
    tts.write_to_fp(audio_file)
    audio_file.seek(0)
    return audio_file

# Custom CSS for a fun and unique interface
def set_custom_theme():
    st.markdown(
        """
        <style>
        .main {
            background: linear-gradient(to right, #1e3c72, #2a5298);
            color: white;
        }
        .stApp {
            max-width: 1000px;
            margin: 0 auto;
        }
        h1 {
            color: #FFD700;
            text-shadow: 2px 2px 4px #000000;
            font-size: 3.5em;
            text-align: center;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0% {
                transform: scale(1);
            }
            50% {
                transform: scale(1.05);
            }
            100% {
                transform: scale(1);
            }
        }
        .upload-box {
            border: 3px dashed #FFD700;
            border-radius: 20px;
            padding: 30px;
            text-align: center;
            margin: 20px 0;
            background-color: rgba(0, 0, 0, 0.3);
        }
        .censored-badge {
            display: inline-block;
            background-color: #FF4500;
            color: white;
            padding: 5px 10px;
            border-radius: 15px;
            font-weight: bold;
            margin: 5px;
        }
        .stButton button {
            background-color: #FF4500;
            color: white;
            font-weight: bold;
            padding: 10px 25px;
            border-radius: 10px;
            border: none;
            transition: all 0.3s;
        }
        .stButton button:hover {
            background-color: #FFD700;
            color: black;
            transform: scale(1.05);
        }
        .result-box {
            background-color: rgba(0, 0, 0, 0.5);
            border-radius: 15px;
            padding: 20px;
            margin: 20px 0;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

def display_fun_facts():
    fun_facts = [
        "The average person swears about 80 times per day.",
        "Studies show that swearing can actually increase pain tolerance.",
        "The censorship sound 'BEEP' dates back to the early days of radio and TV broadcasting.",
        "In medieval times, swear words were often related to religious blasphemy.",
        "Some languages have more than twice as many swear words as others.",
        "The first recorded use of censorship beeps on television was in the 1950s.",
        "Different cultures have wildly different taboo words and phrases.",
        "Swearing in a foreign language activates different parts of the brain than swearing in your native tongue.",
        "The dolphin sound is sometimes used as a censor because dolphins make high-pitched sounds similar to TV beeps.",
        "Some streaming platforms employ AI to detect and censor profanity in real-time."
    ]
    
    st.sidebar.markdown("### 🎓 **Did You Know?**")
    st.sidebar.info(random.choice(fun_facts))

def main():
    set_custom_theme()
    
    # Load bad words
    bad_words_file_path = "en.txt"
    try:
        with open(bad_words_file_path, 'r') as file:
            bad_words = file.read().splitlines()
    except FileNotFoundError:
        # Fallback list of bad words in case the file isn't found
        bad_words = ["damn", "hell", "shit", "fuck", "ass", "bastard", "crap"]
    
    # ASCII Art Title
    st.markdown("""
    <div style="text-align: center; margin-bottom: 30px;">
        <h1>🔊 VulgarVeto 🚫</h1>
        <p style="font-size: 1.2em; color: #FFD700;">
            Keep it clean, keep it mean, bleep that obscene!
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Fun audio meter animation
    st.markdown("""
    <div style="display: flex; justify-content: center; margin: 20px 0;">
        <div style="width: 10px; height: 20px; background-color: #FFD700; margin: 0 2px; animation: equalize 1s infinite;"></div>
        <div style="width: 10px; height: 40px; background-color: #FFD700; margin: 0 2px; animation: equalize 0.8s infinite;"></div>
        <div style="width: 10px; height: 15px; background-color: #FFD700; margin: 0 2px; animation: equalize 1.2s infinite;"></div>
        <div style="width: 10px; height: 30px; background-color: #FFD700; margin: 0 2px; animation: equalize 0.6s infinite;"></div>
        <div style="width: 10px; height: 25px; background-color: #FFD700; margin: 0 2px; animation: equalize 1.3s infinite;"></div>
        <div style="width: 10px; height: 45px; background-color: #FFD700; margin: 0 2px; animation: equalize 0.7s infinite;"></div>
        <div style="width: 10px; height: 20px; background-color: #FFD700; margin: 0 2px; animation: equalize 1.1s infinite;"></div>
    </div>
    <style>
    @keyframes equalize {
        0% { transform: scaleY(1); }
        50% { transform: scaleY(0.6); }
        100% { transform: scaleY(1); }
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Add tabs for different features
    tabs = st.tabs(["🎤 Audio Filter", "ℹ️ About", "⚙️ Settings"])
    
    with tabs[0]:
        st.markdown('<div class="upload-box">', unsafe_allow_html=True)
        uploaded_file = st.file_uploader("**Drop your potentially vulgar audio here**", type=["wav"])
        st.markdown('</div>', unsafe_allow_html=True)
        
        if uploaded_file:
            st.audio(uploaded_file, format='audio/wav')
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### Censorship Style")
                censor_type = st.selectbox(
                    "Choose how to censor bad words:",
                    ["Classic BEEP", "Random", "Dolphin", "Symbols"]
                )
            with col2:
                st.markdown("### Processing Method")
                chunk_duration = st.slider("Chunk duration (ms)", 5000, 30000, 15000, 5000)
            
            with st.spinner("🔍 Running voice recognition..."):
                if st.button("🚫 Clean My Audio!"):
                    # Add progress bar for visual feedback
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    # Simulate processing steps for better user experience
                    status_text.text("Analyzing audio...")
                    progress_bar.progress(10)
                    time.sleep(0.5)
                    
                    status_text.text("Transcribing content...")
                    progress_bar.progress(30)
                    transcription = transcribe_audio(uploaded_file, chunk_duration)
                    
                    status_text.text("Detecting naughty words...")
                    progress_bar.progress(60)
                    time.sleep(0.5)
                    
                    status_text.text("Applying censorship...")
                    progress_bar.progress(80)
                    filtered_text = filter_bad_words(transcription, bad_words, censor_type)
                    
                    status_text.text("Generating clean audio...")
                    progress_bar.progress(90)
                    filtered_audio = text_to_speech(filtered_text)
                    
                    progress_bar.progress(100)
                    status_text.text("Complete! 🎉")
                    time.sleep(1)
                    progress_bar.empty()
                    status_text.empty()
                    
                    # Calculate profanity stats
                    total_words = len(transcription.split())
                    bad_word_count = sum(1 for word in transcription.lower().split() 
                                         if any(bad_word in word for bad_word in bad_words))
                    profanity_percentage = (bad_word_count / total_words) * 100 if total_words > 0 else 0
                    
                    # Display results
                    st.markdown('<div class="result-box">', unsafe_allow_html=True)
                    
                    # Add profanity meter
                    st.markdown(f"""
                    ### Profanity Meter 🌡️
                    <div style="width: 100%; background-color: #e0e0e0; border-radius: 10px; height: 30px; margin: 10px 0;">
                        <div style="width: {min(profanity_percentage, 100)}%; background: linear-gradient(to right, green, {'yellow' if profanity_percentage < 50 else 'red'}); 
                        height: 100%; border-radius: 10px; text-align: center; line-height: 30px; color: white; font-weight: bold;">
                            {profanity_percentage:.1f}%
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if profanity_percentage > 50:
                        st.warning("Whoa there, sailor! That's some colorful language you've got! 🚢")
                    elif profanity_percentage > 20:
                        st.info("Hmm, you could use a little soap in that mouth! 🧼")
                    else:
                        st.success("Pretty clean! Just a few touch-ups needed. ✨")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("### Original Transcription")
                        st.write(transcription)
                    
                    with col2:
                        st.markdown("### Censored Version")
                        st.write(filtered_text)
                    
                    st.markdown("### Cleaned Audio")
                    st.audio(filtered_audio, format='audio/wav')
                    
                    st.markdown("</div>", unsafe_allow_html=True)
                    
                    # Show some censored words tags
                    st.markdown("### Detected Bad Words:")
                    if bad_word_count > 0:
                        detected_words = []
                        for word in transcription.lower().split():
                            for bad_word in bad_words:
                                if bad_word in word and bad_word not in detected_words:
                                    detected_words.append(bad_word)
                        
                        if detected_words:
                            st.markdown('<div style="display: flex; flex-wrap: wrap;">', unsafe_allow_html=True)
                            for word in detected_words[:10]:  # Show max 10 words
                                st.markdown(f'<span class="censored-badge">{word[0]}{"*" * (len(word)-1)}</span>', unsafe_allow_html=True)
                            st.markdown('</div>', unsafe_allow_html=True)
                    else:
                        st.success("No bad words detected! 👏")
    
    with tabs[1]:
        st.markdown("""
        ## About VulgarVeto
        
        **VulgarVeto** is your solution to clean up foul-mouthed audio! Whether you're preparing content for:
        
        - 👪 Family-friendly platforms
        - 🏫 Educational settings
        - 📱 Social media that restricts profanity
        - 🎭 Comedy that needs strategic bleeps
        
        Our advanced algorithm detects and censors inappropriate language while preserving the meaning and flow of the original audio.
        
        ### How It Works
        
        1. 🎤 **Upload** - Provide an audio file in WAV format
        2. 🧠 **Process** - Our AI transcribes the audio and identifies problematic words
        3. 🚫 **Censor** - We replace bad words with your chosen censorship style
        4. 🔊 **Output** - Get a clean version ready for your audience!
        
        ### Censorship Styles
        
        - **Classic BEEP** - The traditional censorship sound
        - **Random** - Various unexpected replacements
        - **Dolphin** - Marine-themed censorship (🐬🐬🐬)
        - **Symbols** - Replaces words with symbols (#@$%!)
        """)
    
    with tabs[2]:
        st.markdown("## Settings")
        st.write("Customize your VulgarVeto experience:")
        
        # Voice selection for TTS (for demonstration - actual functionality would require additional code)
        st.selectbox("TTS Voice", ["Standard Female", "Standard Male", "Robot", "Posh British", "Valley Girl"], index=0)
        
        # Sensitivity slider
        sensitivity = st.slider("Profanity Detection Sensitivity", 1, 10, 5)
        st.caption(f"Current setting: {'Low' if sensitivity < 4 else 'High' if sensitivity > 7 else 'Medium'} sensitivity")
        
        # Advanced options
        with st.expander("Advanced Options"):
            st.checkbox("Block mild profanity", value=True)
            st.checkbox("Block moderate profanity", value=True)
            st.checkbox("Block severe profanity", value=True)
            st.checkbox("Use AI-enhanced detection", value=True)
            st.checkbox("Keep original audio timing", value=False)
    
    # Sidebar content
    st.sidebar.image("https://www.crazysocks.com/cdn/shop/articles/benefits-of-swearing_800x.png?v=1688849137", use_column_width=True)
    display_fun_facts()
    
    # Add random quotes about censorship to the sidebar - FIXED QUOTE MARKS HERE
    quotes = [
        "\"Censorship is telling a man he can't have a steak just because a baby can't chew it.\" - Mark Twain",
        "\"The first condition of progress is the removal of censorship.\" - George Bernard Shaw",
        "\"Censorship reflects a society's lack of confidence in itself.\" - Potter Stewart",
        "\"I don't see why someone should lose their life just so you can have a snack.\" - Captain Obvious",
        "\"BEEP out of my way, I'm trying to BEEP make a point here!\" - Censored Comedian",
        "\"The BEEP is always BEEP-er on the other side.\" - Anonymous",
        "\"To BEEP, or not to BEEP, that is the BEEP question.\" - William ShakesBEEP"
    ]
    
    st.sidebar.markdown("### 💭 **Quotable Quotes**")
    st.sidebar.markdown(f"*{random.choice(quotes)}*")
    
    # Footer
    st.markdown("""
    <div style="text-align: center; margin-top: 50px; padding: 20px; background-color: rgba(0,0,0,0.5); border-radius: 10px;">
        <p>Made with 🤐 by VulgarVeto Team</p>
        <p style="font-size: 0.8em;">We believe in your right to be clean... and your right to be dirty, just not in public!</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()