# AI-Powered Video Audio Replacement

This project uses Streamlit to replace the audio of a video with an AI-generated voice. The pipeline involves:
1. Extracting the audio of a video.
2. Transcribing the audio file with GCP's Speech to text API
3. Correcting the transcription using Azure OpenAI GPT-4.
4. Generating speech from the corrected transcription using Google Text-to-Speech.
5. Replacing the original video's audio with the new AI-generated voice.

## How to Run

1. Copy the sample environment file and set up your environment variables:
    ```bash
    cp .env.sample .env
    ```
   Open the `.env` file and fill in your actual API keys and other required variables.

2. Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

3. Run the Streamlit app:
    ```bash
    streamlit run app.py
    ```

4. Upload a video and let the app replace its audio with AI.

## Environment Variables

Make sure to set the following environment variables in your `.env` file:

- `GOOGLE_APPLICATION_CREDENTIALS`: Path to your Google Cloud service account key file
- `AZURE_API_KEY`: Your Azure OpenAI API key
- `AZURE_API_URL`: Your Azure OpenAI API endpoint

Remember to never commit your `.env` file to version control. It's already included in the `.gitignore` file to prevent accidental commits.