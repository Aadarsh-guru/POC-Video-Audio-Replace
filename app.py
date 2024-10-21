import streamlit as st
import os
import tempfile
import requests
from google.cloud import speech
from google.cloud import texttospeech
from moviepy.editor import VideoFileClip, AudioFileClip
from dotenv import load_dotenv
import wave
import time
from pydub import AudioSegment
import librosa
import soundfile as sf

# Load environment variables from .env file
load_dotenv()

# Set Google Cloud credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
# Azure API credentials
api_key = os.getenv("AZURE_API_KEY")
api_url = os.getenv("AZURE_API_URL")

# Function to get sample rate from audio file
def get_audio_sample_rate(audio_path):
    with wave.open(audio_path, 'rb') as wf:
        sample_rate = wf.getframerate()
    return sample_rate

# Function to convert audio to mono and adjust sample rate if needed
def convert_audio_to_mono(audio_path):
    try:
        audio = AudioSegment.from_wav(audio_path)
        audio = audio.set_channels(1)  # Convert to mono
        audio = audio.set_frame_rate(16000)  # Set sample rate to 16kHz
        mono_audio_path = audio_path.replace(".wav", "_mono.wav")
        audio.export(mono_audio_path, format="wav")
        return mono_audio_path
    except Exception as e:
        st.error(f"Error converting audio: {str(e)}")
        return None

# Transcribe audio using Google Speech-to-Text
def transcribe_audio(audio_path):
    try:
        client = speech.SpeechClient()
        mono_audio_path = convert_audio_to_mono(audio_path)
        if not mono_audio_path:
            raise Exception("Failed to convert audio to mono.")
        with open(mono_audio_path, 'rb') as audio_file:
            content = audio_file.read()
        audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code='en-US'
        )
        response = client.recognize(config=config, audio=audio)
        transcript = ' '.join([result.alternatives[0].transcript for result in response.results])
        if not transcript:
            raise Exception("Transcription returned empty.")
        return transcript
    except Exception as e:
        st.error(f"Error transcribing audio: {str(e)}")
        return None

# Correct transcription using GPT-4o (Azure API)
def correct_transcription(transcript):
    headers = {"api-key": api_key, "Content-Type": "application/json"}
    data = {
        "messages": [
            {"role": "system", "content": "Correct the grammar and remove filler words."},
            {"role": "user", "content": transcript}
        ],
        "max_tokens": 500
    }
    try:
        response = requests.post(api_url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        st.error(f"Error correcting transcription: {str(e)}")
        return None

# Generate speech using Google Text-to-Speech
def text_to_speech(text):
    try:
        client = texttospeech.TextToSpeechClient()
        input_text = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(language_code="en-US", name="en-US-Journey-D")
        audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
        
        response = client.synthesize_speech(input=input_text, voice=voice, audio_config=audio_config)
        return response.audio_content
    except Exception as e:
        st.error(f"Error generating speech: {str(e)}")
        return None

# Extract audio from video file
def extract_audio_from_video(video_path):
    try:
        video = VideoFileClip(video_path)
        audio_path = video_path.replace(".mp4", ".wav")
        # Force a higher sample rate if needed
        video.audio.write_audiofile(audio_path, codec='pcm_s16le', fps=16000)
        video.close()
        return audio_path
    except Exception as e:
        st.error(f"Error extracting audio from video: {str(e)}")
        return None

def convert_mp3_to_wav(mp3_path):
    wav_path = mp3_path.replace('.mp3', '.wav')
    audio = AudioSegment.from_mp3(mp3_path)
    audio.export(wav_path, format="wav")
    return wav_path

def replace_audio_in_video(video_path, audio_path, output_path):
    try:
        video = VideoFileClip(video_path)
        if audio_path.endswith('.mp3'):
            audio_path = convert_mp3_to_wav(audio_path)
        new_audio = AudioFileClip(audio_path)
        video_duration = video.duration
        audio_duration = new_audio.duration
        if abs(video_duration - audio_duration) > 0.5:
            y, sr = librosa.load(audio_path)
            y_stretched = librosa.effects.time_stretch(y, rate=audio_duration/video_duration)
            stretched_audio_path = audio_path.replace(".wav", "_stretched.wav")
            sf.write(stretched_audio_path, y_stretched, sr)
            new_audio = AudioFileClip(stretched_audio_path)
        video = video.set_audio(new_audio)
        video.write_videofile(output_path, codec='libx264', audio_codec='aac')
        video.close()
        new_audio.close()
        if 'stretched_audio_path' in locals():
            try:
                os.remove(stretched_audio_path)
            except Exception as e:
                st.warning(f"Could not delete temp file: {stretched_audio_path}. Error: {str(e)}")
        return True
    except Exception as e:
        st.error(f"Error replacing audio: {str(e)}")
        return False

def safe_file_cleanup(file_path, retries=5, delay=1):
    for i in range(retries):
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
            return
        except PermissionError:
            if i < retries - 1:
                time.sleep(delay)
            else:
                st.warning(f"Could not delete temp file after {retries} attempts: {file_path}")

def main():
    st.title("AI-Powered Video Audio Replacement")

    # File uploader for video
    uploaded_video = st.file_uploader("Upload a video file (max 1 minute)", type=["mp4", "mov", "avi", "webm"])

    if uploaded_video:
        
        with st.spinner("Processing video..."):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_video:
                temp_video.write(uploaded_video.read())
                temp_video_path = temp_video.name
 
            if uploaded_video:
                video_length = VideoFileClip(temp_video_path).duration
        
            if video_length > 60:
                st.error("Video must be less than 1 minute.")
                return

            # Step 1: Extract audio from video
            st.info("Extracting audio from the video...")
            audio_path = extract_audio_from_video(temp_video_path)

            if audio_path:
                # Step 2: Transcribe the audio
                st.info("Transcribing audio...")
                transcript = transcribe_audio(audio_path)
                if transcript:
                    st.text_area("Transcribed Text:", transcript, height=100)

                    # Step 3: Correct the transcription using GPT-4o
                    st.info("Correcting transcription...")
                    corrected_transcript = correct_transcription(transcript)
                    if corrected_transcript:
                        st.text_area("Corrected Transcription:", corrected_transcript, height=100)

                        # Step 4: Generate new audio using Google Text-to-Speech
                        st.info("Generating new audio...")
                        new_audio_content = text_to_speech(corrected_transcript)
                        if new_audio_content:
                            st.audio(new_audio_content, format="audio/mp3")

                            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio:
                                temp_audio.write(new_audio_content)
                                temp_audio_path = temp_audio.name

                            # Step 5: Replace the audio in the video
                            st.info("Replacing audio in the video...")
                            output_video_path = temp_video_path.replace(".mp4", "_with_new_audio.mp4")
                            if replace_audio_in_video(temp_video_path, temp_audio_path, output_video_path):
                                st.success("Audio replaced successfully!")
                                st.video(output_video_path)

                                # Download button for the processed video
                                with open(output_video_path, "rb") as file:
                                    btn = st.download_button(
                                        label="Download processed video",
                                        data=file,
                                        file_name="processed_video.mp4",
                                        mime="video/mp4"
                                    )

             # Clean up temporary files
            for file_path in [temp_video_path, audio_path, temp_audio_path, output_video_path]:
                safe_file_cleanup(file_path)

if __name__ == "__main__":
    main()