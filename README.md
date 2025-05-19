# Enhanced HIBP Checker 

**Enhanced HIBP Checker** is a desktop application written in mostly python designed to help you enhance your online security. It allows you to check email addresses or usernames against the Have I Been Pwned (HIBP) database for known data breaches and provides AI-powered advice on cybersecurity matters using a local Ollama instance.

## Features

*   **HIBP Check:** Securely check if your account details have been compromised in known data breaches.
*   **AI Advisor:** Engage in a conversation with a local AI model (via Ollama) for:
    *   Personalized advice based on HIBP breach results.
    *   General guidance on creating strong passwords.
    *   Answers to other cybersecurity questions.
*   **Secure API Key Storage:** Your HIBP API key is stored securely in your system's keyring, not in plain text.
*   **Local AI Processing:** All AI interactions are processed locally using Ollama, ensuring your conversations remain private.
*   **Customizable Settings:**
    *   Configure your HIBP API key.
    *   Set the Ollama API endpoint.
    *   Select your preferred Ollama model from your local installation.

## Prerequisites

Before you begin, ensure you have the following installed:

*   **Python:** Version 3.7 or newer.
*   **Ollama:** Download and install Ollama from [https://ollama.com/](https://ollama.com/).
    *   Ensure Ollama is running before using the AI Advisor.
    *   It is recommended to use Ollama version 0.1.32 or later for full compatibility with the model selection feature (which uses `/api/tags`). Always use the latest Ollama version for security updates.
*   **Git:** For cloning the repository.

## Setup Instructions

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/MRFrazer25/HIBP_App_AI
    cd HIBP_App_AI
    ```

2.  **Create and Activate a Virtual Environment:**
    *   **Windows:**
        ```bash
        python -m venv venv
        venv\Scripts\activate
        ```
    *   **macOS/Linux:**
        ```bash
        python3 -m venv venv
        source venv/bin/activate
        ```

3.  **Install Python Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    This will install `PyQt6`, `requests`, `keyring`, and other necessary packages.

4.  **Prepare Ollama:**
    *   Ensure Ollama is installed and running.
    *   Pull a model to use with the AI Advisor. For example:
        ```bash
        ollama pull phi4:mini
        ```
    *   Make sure the model is running by doing:
        ```bash
        ollama run phi4-mini
        ```
        Other models like `llama3:8b` can also be used. The application allows you to select from any model you have pulled into your local Ollama instance.

5.  **Run the Application:**
    ```bash
    python main.py
    ```

## Usage Guide

1.  **First-Time Setup (Settings Tab):**
    *   Navigate to the **Settings** tab.
    *   **HIBP API Key:** Enter your HIBP API key (get one from [Have I Been Pwned](https://haveibeenpwned.com/API/Key)) and click "Save HIBP API Key".
    *   **Ollama Settings:**
        *   The Ollama API endpoint usually defaults to `http://localhost:11434/api/generate`. Adjust if your Ollama setup is different.
        *   Click "Refresh Models" to load your locally installed Ollama models into the dropdown.
        *   Select your preferred model from the list.
        *   Click "Save Ollama Settings".

2.  **HIBP Checker Tab:**
    *   Enter an email address or username you want to check.
    *   Click "Check for Breaches". Results will appear below.
    *   If breaches are found, you can click "Get AI Advice on These Breaches" to automatically send the breach details to the AI Advisor for recommendations.

3.  **AI Advisor Tab:**
    *   Ensure Ollama is running and configured in Settings.
    *   Type your cybersecurity-related questions or prompts into the input field.
    *   Press Enter or click "Send". The AI will stream its response into the chat window.

## Security and Privacy

*   **HIBP API Key:** Your HIBP API key is stored using the `keyring` library, which leverages your operating system's native credential manager (e.g., Windows Credential Manager, macOS Keychain, Linux Secret Service). It is not stored in plain text by the application.
*   **Ollama Interactions:** All communication with the AI model via Ollama is done locally on your machine. Your prompts and the AI's responses are not sent to any external cloud services by this application. Data privacy depends on the Ollama setup and the models you use.
*   **Data Input:** Be mindful of the data you input into the HIBP check and AI advisor. While the application aims for local processing, always exercise caution with sensitive personal information.
*   **No Data Collection:** This application does not collect or transmit any personal data or usage statistics.

## Troubleshooting

*   **"Could not connect to Ollama..." / AI Advisor not working:**
    *   Ensure Ollama is installed and running on your system. You can usually check this by opening a terminal and typing `ollama list`.
    *   Verify the Ollama API endpoint in the Settings tab is correct (default: `http://localhost:11434/api/generate`).
    *   Make sure you have pulled at least one model into Ollama (such as `ollama pull phi4:mini`).

*   **"Error saving/retrieving HIBP API Key..." / Keyring issues:**
    *   The `keyring` library depends on a system-level credential store. On some Linux distributions, you might need to install additional packages (such as `gnome-keyring` or `kwallet`) and ensure a D-Bus session is active.
    *   If errors persist, consult the `keyring` library documentation for backend-specific troubleshooting.
*   **Application Fails to Start / Missing Dependencies:**
    *   Ensure you have activated your Python virtual environment before running `pip install -r requirements.txt` and `python main.py`.
    *   Check for any error messages during `pip install` that might indicate missing system libraries needed by PyQt6 or other dependencies.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.