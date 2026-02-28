# Personal AI Assistant (Phase 1)

This project runs a Python Flask web server that connects WhatsApp (via Twilio) to Claude AI (Anthropic) to act as a personal life assistant ("Jarvis"). It saves conversational history in a Neon PostgreSQL database.

## Prerequisites

1. **Python 3.8+**
2. **Twilio Account** (with a WhatsApp Sandbox or Approved Number)
3. **Anthropic Account** (API Key for Claude)
4. **Neon PostgreSQL Database** (Connection String)
5. **Render Account** (for deployment)

## Setup Locally

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment Variables:**
   - Copy `.env.example` to `.env`
   - Fill in your actual credentials in the `.env` file.

3. **Database Setup:**
   - Go to your Neon Dashboard -> SQL Editor
   - Copy the contents of `database.sql` and run it to create the `messages` table.

4. **Run the App Locally:**
   ```bash
   python app.py
   ```
   (The server will start on port 5000)

## Connecting Twilio to Your Local Server

To test locally with WhatsApp, you need to expose your local server to the public internet using `ngrok`.

1. Run ngrok:
   ```bash
   ngrok http 5000
   ```
2. Copy the `https://xxxx-xxx.ngrok.io` URL.
3. Go to Twilio -> WhatsApp Sandbox Settings.
4. Set the webhook URL for "WHEN A MESSAGE COMES IN" to `https://xxxx-xxx.ngrok.io/webhook`.
5. Send a WhatsApp message to your Twilio number to test.

## Deployment to Render.com

1. Create a new **Web Service** on Render.
2. Connect your GitHub repository.
3. Configuration:
   - **Environment:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
4. Add your **Environment Variables** securely in the Render dashboard.
5. Deploy.
6. Once deployed, update your Twilio Webhook URL to your new Render URL: `https://your-render-app.onrender.com/webhook`.
