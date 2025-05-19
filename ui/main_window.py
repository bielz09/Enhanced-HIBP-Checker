"""
Main window for the application.

This file defines the main graphical user interface (GUI) using PyQt6.
It includes tabs for:
- HIBP (Have I Been Pwned) account checking.
- AI Advisor chat powered by Ollama.
- Settings for API keys and Ollama configuration.

It handles interactions with the HIBP API, Ollama API (via a worker thread
for non-blocking operation), and secure storage for the HIBP API key.
"""
from PyQt6.QtWidgets import QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QMessageBox, QApplication, QComboBox
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSettings, QUrl
from .styles import DARK_MODE_STYLESHEET
from core.secure_storage import set_api_key, get_api_key
from core.hibp_client import check_hibp, HibpError
import requests
import json
import os
import sys
import html

# Constants for QSettings
ORG_NAME = "HIBPappOrg"
APP_NAME = "HIBPapp"
SETTINGS_OLLAMA_ENDPOINT = "ollama/endpoint"
SETTINGS_OLLAMA_MODEL = "ollama/model"
DEFAULT_OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"
DEFAULT_OLLAMA_MODEL = "phi4-mini"
CHAT_HTML_PATH = os.path.join(os.path.dirname(__file__), "html", "chat_template.html")

# Worker Thread for AI Interaction
class OllamaWorker(QThread):
    """
    Runs Ollama API call in a separate thread to keep the UI responsive.

    Emits signals for streaming results, completion, and errors.
    """
    result = pyqtSignal(dict)  # Emit chunks for streaming
    finished_streaming = pyqtSignal() # Signal when streaming is done
    error = pyqtSignal(str)   # Signal emitting error messages

    def __init__(self, endpoint, model, prompt):
        super().__init__()
        self.endpoint = endpoint
        self.model = model
        self.prompt = prompt
        self._is_running = True

    def run(self):
        """Execute the network request to Ollama and stream results."""
        try:
            payload = {
                "model": self.model,
                "prompt": self.prompt,
                "stream": True  # Enable streaming
            }
            with requests.post(self.endpoint, json=payload, timeout=60, stream=True) as response:
                response.raise_for_status()
                for chunk in response.iter_lines():
                    if not self._is_running:
                        break
                    if chunk:
                        try:
                            data = json.loads(chunk.decode('utf-8'))
                            self.result.emit(data) # Emit the parsed JSON chunk
                            if data.get("done"): # Check if Ollama signaled completion of the stream
                                break # Last chunk often has a done flag
                        except json.JSONDecodeError as e_json:
                            # Log decoding errors, but attempt to continue if possible
                            print(f"OllamaWorker: Error decoding JSON chunk: {e_json}. Chunk: {chunk[:100]}...", file=sys.stderr)
                            pass 
        except requests.exceptions.ConnectionError:
            self.error.emit(f"ConnectionError: Could not connect to Ollama at {self.endpoint}. Is Ollama running?")
        except requests.exceptions.Timeout:
            self.error.emit(f"TimeoutError: The request to Ollama timed out.")
        except requests.exceptions.RequestException as e:
            self.error.emit(f"RequestError: An error occurred: {e}")
        except Exception as e:
            self.error.emit(f"UnexpectedError: An unexpected error occurred in AI worker: {e}")
        finally:
            if self._is_running:
                self.finished_streaming.emit()

    def stop(self):
        """Signals the worker thread to stop processing."""
        self._is_running = False

class MainWindow(QMainWindow):
    def __init__(self):
        """
        Initializes the main application window, sets up UI tabs,
        and loads settings.
        """
        super().__init__()
        self.setWindowTitle("Enhanced HIBP Checker")
        self.setGeometry(100, 100, 900, 600) # Adjusted height slightly
        self.setStyleSheet(DARK_MODE_STYLESHEET)

        self.settings = QSettings(ORG_NAME, APP_NAME)
        self.chat_html_url = QUrl.fromLocalFile(CHAT_HTML_PATH)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.chat_view_ready = False
        self.pending_js_calls = []

        self._create_hibp_tab()
        self._create_ai_advisor_tab()
        self._create_settings_tab()

        self.ollama_worker = None
        self.current_ai_response_text = ""
        self.current_ai_message_dom_id = None
        self.hibp_context_for_ai = None

        self.tabs.addTab(self.hibp_tab, "HIBP Check")
        self.tabs.addTab(self.ai_advisor_tab, "AI Advisor")
        self.tabs.addTab(self.settings_tab, "Settings")

    def _js_escape(self, text: str) -> str:
        """Escape string for safe insertion into JavaScript single-quoted string."""
        # Escapes backslashes, single quotes, and newlines/carriage returns.
        return text.replace('\\', '\\\\').replace("\'", "\\'").replace('\n', '\\n').replace('\r', '\\r')

    def _create_hibp_tab(self):
        """Creates and configures the HIBP Check tab UI elements."""
        self.hibp_tab = QWidget()
        layout = QVBoxLayout(self.hibp_tab)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout.addWidget(QLabel("Enter Email or Username to Check:"))
        self.hibp_input = QLineEdit()
        layout.addWidget(self.hibp_input)

        self.hibp_check_button = QPushButton("Check for Breaches")
        self.hibp_check_button.clicked.connect(self._run_hibp_check)
        layout.addWidget(self.hibp_check_button)

        self.hibp_results_area = QTextEdit()
        self.hibp_results_area.setReadOnly(True)
        layout.addWidget(self.hibp_results_area)

        self.hibp_ai_advice_button = QPushButton("Get AI Advice on These Breaches")
        self.hibp_ai_advice_button.clicked.connect(self._request_ai_advice_on_hibp)
        self.hibp_ai_advice_button.setEnabled(False) # Initially disabled
        layout.addWidget(self.hibp_ai_advice_button)

        self.tabs.addTab(self.hibp_tab, "HIBP Check")

    def _on_chat_view_load_finished(self, success: bool):
        """Handles the event when the AI chat QWebEngineView has finished loading its content."""
        if success:
            # The HTML/JS side will now handle waiting for marked.js to be ready.
            self.chat_view_ready = True 
            # Process any pending JS calls
            for js_code, callback in self.pending_js_calls:
                if callback:
                    self.ai_chat_view.page().runJavaScript(js_code, callback)
                else:
                    self.ai_chat_view.page().runJavaScript(js_code)
            self.pending_js_calls = []
            
            self.ai_send_button.setEnabled(True)
            self.ai_input.setEnabled(True)
        else:
            self.chat_view_ready = False 
            QMessageBox.critical(self, "Chat Error", "Failed to load the chat interface. AI Advisor may not work correctly.")
            self.ai_send_button.setEnabled(False)
            self.ai_input.setEnabled(False)

    def _run_chat_js(self, js_code: str, callback=None):
        """Executes JavaScript code in the AI chat QWebEngineView.

        If the view is not ready, the call is queued.
        """
        if self.chat_view_ready:
            if callback:
                self.ai_chat_view.page().runJavaScript(js_code, callback)
            else:
                self.ai_chat_view.page().runJavaScript(js_code)
        else:
            self.pending_js_calls.append((js_code, callback))

    def _create_ai_advisor_tab(self):
        """Creates and configures the AI Advisor tab UI elements, including the QWebEngineView for chat."""
        self.ai_advisor_tab = QWidget()
        layout = QVBoxLayout(self.ai_advisor_tab)

        self.ai_chat_view = QWebEngineView()
        self.ai_chat_view.page().loadFinished.connect(self._on_chat_view_load_finished)
        self.ai_chat_view.setUrl(self.chat_html_url)
        layout.addWidget(self.ai_chat_view)

        input_layout = QHBoxLayout() # For input field and send button
        self.ai_input = QLineEdit()
        self.ai_input.setPlaceholderText("Ask the AI for advice...")
        self.ai_input.returnPressed.connect(self._send_ai_message)
        self.ai_input.setEnabled(False) # Initially disable until chat view is ready
        input_layout.addWidget(self.ai_input)

        self.ai_send_button = QPushButton("Send")
        self.ai_send_button.clicked.connect(self._send_ai_message)
        self.ai_send_button.setEnabled(False) # Initially disable until chat view is ready
        input_layout.addWidget(self.ai_send_button)
        layout.addLayout(input_layout)

        self.tabs.addTab(self.ai_advisor_tab, "AI Advisor")

    def _create_settings_tab(self):
        """Creates and configures the Settings tab UI elements for API keys and Ollama settings."""
        self.settings_tab = QWidget()
        layout = QVBoxLayout(self.settings_tab)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout.addWidget(QLabel("HIBP API Key:"))
        self.api_key_input = QLineEdit()
        stored_api_key = get_api_key()
        if stored_api_key:
            self.api_key_input.setText(stored_api_key)
        layout.addWidget(self.api_key_input)

        self.save_api_key_button = QPushButton("Save HIBP API Key")
        self.save_api_key_button.clicked.connect(self._save_hibp_api_key)
        layout.addWidget(self.save_api_key_button)

        self.api_key_status_label = QLabel("")
        layout.addWidget(self.api_key_status_label)

        # Ollama Endpoint
        layout.addWidget(QLabel("Ollama API Endpoint:"))
        self.ollama_endpoint_input = QLineEdit()
        self.ollama_endpoint_input.setText(self.settings.value(SETTINGS_OLLAMA_ENDPOINT, DEFAULT_OLLAMA_ENDPOINT))
        layout.addWidget(self.ollama_endpoint_input)

        # Ollama Model Selection
        layout.addWidget(QLabel("Ollama Model:"))
        self.ollama_model_combo = QComboBox()
        layout.addWidget(self.ollama_model_combo)
        self.refresh_models_button = QPushButton("Refresh Models")
        self.refresh_models_button.clicked.connect(self._populate_ollama_models)
        layout.addWidget(self.refresh_models_button)

        self.save_ollama_settings_button = QPushButton("Save Ollama Settings")
        self.save_ollama_settings_button.clicked.connect(self._save_ollama_settings)
        layout.addWidget(self.save_ollama_settings_button)
        self.ollama_settings_status_label = QLabel("")
        layout.addWidget(self.ollama_settings_status_label)

        self.tabs.addTab(self.settings_tab, "Settings")
        self._populate_ollama_models() # Initial population attempt

    def _save_hibp_api_key(self):
        """Saves the HIBP API key entered by the user to secure storage."""
        api_key = self.api_key_input.text()
        if api_key:
            try:
                set_api_key(api_key)
                self.api_key_status_label.setText("HIBP API Key saved successfully!")
                self.api_key_status_label.setStyleSheet("color: green;")
            except Exception as e:
                self.api_key_status_label.setText(f"Error saving HIBP API Key: {e}")
                self.api_key_status_label.setStyleSheet("color: red;")
                QMessageBox.critical(self, "Keyring Error", f"Could not save HIBP API key to system keyring: {e}")
        else:
            self.api_key_status_label.setText("HIBP API Key cannot be empty.")
            self.api_key_status_label.setStyleSheet("color: red;")

    def _save_ollama_settings(self):
        """Saves the Ollama endpoint and selected model to application settings."""
        endpoint = self.ollama_endpoint_input.text().strip()
        model = self.ollama_model_combo.currentText()

        if not endpoint:
            self.ollama_settings_status_label.setText("Ollama endpoint cannot be empty.")
            self.ollama_settings_status_label.setStyleSheet("color: red;")
            return

        self.settings.setValue(SETTINGS_OLLAMA_ENDPOINT, endpoint)
        self.settings.setValue(SETTINGS_OLLAMA_MODEL, model)
        self.ollama_settings_status_label.setText("Ollama settings saved!")
        self.ollama_settings_status_label.setStyleSheet("color: green;")

    def _populate_ollama_models(self):
        """Fetches and populates the list of available Ollama models in the settings tab."""
        self.ollama_model_combo.clear()
        self.ollama_model_combo.setEnabled(False)
        self.refresh_models_button.setEnabled(False)
        self.ollama_settings_status_label.setText("Fetching models...")
        self.ollama_settings_status_label.setStyleSheet("color: gray;")
        try:
            endpoint_base = self.settings.value(SETTINGS_OLLAMA_ENDPOINT, DEFAULT_OLLAMA_ENDPOINT)
            if endpoint_base.endswith("/api/generate"):
                tags_endpoint = endpoint_base[:-len("/api/generate")] + "/api/tags"
            elif endpoint_base.endswith("/api/generate/"):
                tags_endpoint = endpoint_base[:-len("/api/generate/")] + "/api/tags"
            else:
                tags_endpoint = endpoint_base.rstrip('/') + "/api/tags"

            response = requests.get(tags_endpoint, timeout=5)
            response.raise_for_status()
            models_data = response.json()
            model_names = [m['name'] for m in models_data.get('models', [])]
            if model_names:
                self.ollama_model_combo.addItems(model_names)
                current_saved_model = self.settings.value(SETTINGS_OLLAMA_MODEL, DEFAULT_OLLAMA_MODEL)
                if current_saved_model in model_names:
                    self.ollama_model_combo.setCurrentText(current_saved_model)
                elif self.ollama_model_combo.count() > 0:
                    self.settings.setValue(SETTINGS_OLLAMA_MODEL, self.ollama_model_combo.itemText(0))
            else:
                self.ollama_settings_status_label.setText("No models found from Ollama.")
                self.ollama_settings_status_label.setStyleSheet("color: orange;")
        except requests.exceptions.RequestException as e:
            self.ollama_settings_status_label.setText(f"Error fetching models: {e}")
            self.ollama_settings_status_label.setStyleSheet("color: red;")
            self.ollama_model_combo.addItem(self.settings.value(SETTINGS_OLLAMA_MODEL, DEFAULT_OLLAMA_MODEL))
        except Exception as e:
            self.ollama_settings_status_label.setText(f"Unexpected error: {e}")
            self.ollama_settings_status_label.setStyleSheet("color: red;")
        finally:
            self.ollama_model_combo.setEnabled(True)
            self.refresh_models_button.setEnabled(True)

    def _handle_start_ai_message_id(self, message_id):
        """Callback from JavaScript, stores the DOM ID of the newly created AI message bubble."""
        self.current_ai_message_dom_id = message_id

    def _prepare_and_send_to_ollama(self, prompt_to_send: str):
        """Prepares the prompt with system instructions and starts the OllamaWorker thread."""
        # This method constructs the final prompt for Ollama, including system
        # instructions for plain text output, and then starts the OllamaWorker thread.
        if self.ollama_worker and self.ollama_worker.isRunning():
            QMessageBox.warning(self, "Busy", "Please wait for the current AI response to complete.")
            return        
        if not self.chat_view_ready:
            QMessageBox.warning(self, "Chat Not Ready", "The AI chat interface is still loading. Please try again shortly.")
            return

        self.ai_send_button.setEnabled(False)
        self.current_ai_response_text = "" 

        js_call = f"startAIMessage('Thinking...');"
        self._run_chat_js(js_call, self._handle_start_ai_message_id)

        ollama_endpoint = self.settings.value(SETTINGS_OLLAMA_ENDPOINT, DEFAULT_OLLAMA_ENDPOINT)
        model_name = self.settings.value(SETTINGS_OLLAMA_MODEL, DEFAULT_OLLAMA_MODEL)

        # System instruction prefix to guide the LLM towards plain text, well-structured output.
        # This is critical for ensuring the AI's response can be safely and cleanly displayed
        # in the chat interface, avoiding markdown or other formatting issues.
        instruction_prefix = (
            "SYSTEM INSTRUCTION: CRITICAL: Your entire response MUST be plain text."
            "ABSOLUTELY NO MARKDOWN formatting is allowed, no exceptions."
            "DO NOT use asterisks (*). DO NOT use hashtags (#). DO NOT use underscores (_). DO NOT use backticks (`)."
            "DO NOT use any characters or syntax for bold, italics, headers, code, or lists that resemble Markdown."
            "If you want to make a list, each item MUST be on a new line, starting with plain text. NO hyphens, NO asterisks."
            "For example, a list should look like this:\\n"
            "Separate paragraphs with a single blank line (two newlines). "
            "Focus on clarity, proper spelling, and grammar. Your output will be displayed as-is, so it must be clean plain text.\\n\\n"
            "Make sure to use the information provided in the context to provide a good quality answer."
        )
        final_prompt = instruction_prefix + prompt_to_send

        self.ollama_worker = OllamaWorker(ollama_endpoint, model_name, final_prompt)
        self.ollama_worker.result.connect(self._handle_ai_stream_chunk)
        self.ollama_worker.finished_streaming.connect(self._ollama_task_concluded)
        self.ollama_worker.error.connect(self._handle_ai_error)
        self.ollama_worker.finished.connect(self._ollama_thread_terminated)
        self.ollama_worker.start()

    def _send_ai_message(self):
        """Handles sending a user's message from the AI input field to the Ollama service."""
        user_input = self.ai_input.text().strip()
        if not user_input:
            return
        
        if not self.chat_view_ready:
            QMessageBox.warning(self, "Chat Not Ready", "The AI chat interface is still loading. Please try sending your message again shortly.")
            return

        escaped_user_input = self._js_escape(user_input)
        self._run_chat_js(f"addUserMessage('{escaped_user_input}');")
        
        self.ai_input.clear()
        self._prepare_and_send_to_ollama(user_input)

    def _handle_ai_stream_chunk(self, chunk_data):
        """Processes a chunk of data received from the Ollama streaming API."""
        token = chunk_data.get("response", "")
        self.current_ai_response_text += token

        if self.current_ai_message_dom_id:
            escaped_full_text = self._js_escape(self.current_ai_response_text)
            js_call = f"updateAIMessageContent('{self.current_ai_message_dom_id}', '{escaped_full_text}');"
            self._run_chat_js(js_call) # Callback not typically needed for updates
        
        QApplication.processEvents()

    def _ollama_task_concluded(self):
        """
        Slot connected to OllamaWorker's finished_streaming signal.
        Indicates the worker has finished its current task (success, stopped, or error).
        Re-enables UI elements. Does not destroy the worker yet.
        """
        # This slot is called when the OllamaWorker emits its custom 'finished_streaming' signal.
        # It means the worker has finished its current attempt (successfully, stopped, or errored).
        self.ai_send_button.setEnabled(True)
        # Do NOT set self.ollama_worker = None here.
        # Reset other UI/state related to an active stream if necessary
        self.current_ai_response_text = ""

    def _ollama_thread_terminated(self):
        """
        Slot connected to QThread.finished signal.
        Indicates the OllamaWorker QThread has fully terminated. Cleans up the worker reference.
        """
        # This slot is called when the QThread's actual run() method has finished and the OS thread is about to terminate.
        # It's connected to QThread.finished.
        if self.ollama_worker: # Check if it's the worker we expect
            try:
                # Disconnect all signals from this specific worker instance
                # to prevent them from being called again if a new worker is made quickly
                # or if this slot is somehow called multiple times for the same worker.
                self.ollama_worker.result.disconnect(self._handle_ai_stream_chunk)
                self.ollama_worker.finished_streaming.disconnect(self._ollama_task_concluded)
                self.ollama_worker.error.disconnect(self._handle_ai_error)
                self.ollama_worker.finished.disconnect(self._ollama_thread_terminated)
            except TypeError:
                # This can happen if a signal was not connected or already disconnected.
                # It's generally safe to ignore.
                pass
            self.ollama_worker = None # Crucial: clear the reference once the thread is truly finished.

    def _show_error_in_ai_bubble(self, message_id, error_text):
        """
        Displays an error message within a specific AI message bubble in the chat UI.

        Args:
            message_id: The DOM ID of the AI message bubble to update.
            error_text: The raw error message to display (will be HTML-escaped).
        """
        # 1. HTML-escape the raw error text to ensure it's treated as plain text by the browser
        html_escaped_error_text = html.escape(error_text)

        # 2. Construct the HTML content string for the bubble.
        content_for_bubble = f"<b>AI:</b><br>Error: {html_escaped_error_text}"
        
        # 3. Escape the entire HTML content string for safe insertion into the JavaScript call
        js_escaped_content_for_call = self._js_escape(content_for_bubble)
        
        js_call = f"updateAIMessageContent('{message_id}', '{js_escaped_content_for_call}');"
        self._run_chat_js(js_call)

    def _handle_ai_error(self, error_message):
        """
        Handles errors signaled by the OllamaWorker.

        Displays the error in the AI chat UI and a system dialog.
        Stops the worker and resets relevant state.
        """
        # error_message is the raw error string. Pass it directly to _show_error_in_ai_bubble,
        # this will handle the necessary escaping.

        if self.current_ai_message_dom_id:
            self._show_error_in_ai_bubble(self.current_ai_message_dom_id, error_message)
        else:
            def on_error_bubble_created(message_id):
                if message_id:
                    self._show_error_in_ai_bubble(message_id, error_message)
                else:
                    pass # Error displaying in chat already handled by _on_chat_view_load_finished logic or main critical
            
            js_call_start_bubble = f"startAIMessage('Error Initializing');"
            self._run_chat_js(js_call_start_bubble, on_error_bubble_created)

        QMessageBox.critical(self, "AI Error", error_message)
        
        self.ai_send_button.setEnabled(True)
        if self.ollama_worker:
            self.ollama_worker.stop() # Ensure worker is stopped
            self.ollama_worker = None
        
        # Reset message-specific state as the attempt is over
        self.current_ai_response_text = ""

    def _run_hibp_check(self):
        """Initiates an HIBP check for the entered account using the stored API key."""
        account = self.hibp_input.text().strip()
        api_key = get_api_key()

        if not account:
            QMessageBox.warning(self, "Input Error", "Please enter an email or username.")
            return

        if not api_key:
            QMessageBox.warning(self, "API Key Missing", "Please set your HIBP API Key in the Settings tab.")
            return

        self.hibp_results_area.setText("Checking...")
        self.hibp_check_button.setEnabled(False) # Disable button during check
        self.hibp_ai_advice_button.setEnabled(False) # Disable advice button during check
        QApplication.processEvents() # Update UI to show "Checking..."

        try:
            breaches = check_hibp(account, api_key)
            if breaches:
                ui_result_text = f"Found {len(breaches)} breach(es) for {account}:\n\n"
                ai_context_parts = [f"Detailed HIBP Check Results for account: {account}"]

                for breach in breaches:
                    title = breach.get('Title', 'N/A')
                    domain = breach.get('Domain', 'N/A')
                    breach_date = breach.get('BreachDate', 'N/A')
                    pwn_count = breach.get('PwnCount', 0)
                    data_classes = ", ".join(breach.get('DataClasses', []))
                    description_html = breach.get('Description', '<p>N/A</p>') # Description is HTML

                    # For UI display (similar to before)
                    ui_result_text += f"- {title} ({breach_date})\n"
                    ui_result_text += f"  Domain: {domain}\n"
                    ui_result_text += f"  Compromised data: {data_classes}\n\n"

                    # For AI context (more detailed)
                    ai_context_parts.append(f"--- Breach Details ---")
                    ai_context_parts.append(f"Title: {title}")
                    ai_context_parts.append(f"Domain: {domain}")
                    ai_context_parts.append(f"BreachDate: {breach_date}")
                    ai_context_parts.append(f"PwnCount: {pwn_count}")
                    ai_context_parts.append(f"DataClasses: {data_classes}")
                    ai_context_parts.append(f"Description (HTML): {description_html}")
                    ai_context_parts.append(f"--- End Breach Details ---")

                self.hibp_results_area.setHtml(ui_result_text.replace('\n', '<br>'))
                self.hibp_context_for_ai = "\n".join(ai_context_parts)
                self.hibp_ai_advice_button.setEnabled(True) # Enable button to get advice
            else:
                self.hibp_results_area.setText(f"No breaches found for {account}.")
                self.hibp_context_for_ai = f"HIBP Check Summary for {account}: No breaches found."
                self.hibp_ai_advice_button.setEnabled(False)

        except HibpError as e:
            self.hibp_results_area.setText(f"Error: {e}")
            QMessageBox.critical(self, "HIBP Error", str(e))
            self.hibp_context_for_ai = None # Clear context on error
            self.hibp_ai_advice_button.setEnabled(False)
        except requests.exceptions.RequestException as e: # Explicitly catch network errors
            self.hibp_results_area.setText(f"Network Error: {e}")
            QMessageBox.critical(self, "Network Error", f"Could not connect to the HIBP service: {e}")
            self.hibp_context_for_ai = None # Clear context on error
            self.hibp_ai_advice_button.setEnabled(False)
        except Exception as e: # Catch other unexpected errors
            self.hibp_results_area.setText(f"An unexpected error occurred: {e}")
            QMessageBox.critical(self, "Error", f"An unexpected error occurred: {e}")
            self.hibp_context_for_ai = None # Clear context on error
            self.hibp_ai_advice_button.setEnabled(False)
        finally:
            self.hibp_check_button.setEnabled(True) # Re-enable button

    def _request_ai_advice_on_hibp(self):
        """
        Requests AI advice based on the results of a previous HIBP check.

        Sends the HIBP context to the AI Advisor tab and Ollama.
        """
        if self.ollama_worker and self.ollama_worker.isRunning():
            QMessageBox.warning(self, "Busy", "Please wait for the current AI response to complete before requesting new advice.")
            return
        
        if not self.chat_view_ready:
            QMessageBox.warning(self, "Chat Not Ready", "The AI chat interface is still loading. Please try again shortly.")
            return

        if not self.hibp_context_for_ai or "No breaches found" in self.hibp_context_for_ai:
            QMessageBox.information(self, "No Breaches", "No breach data available to ask AI for advice. Please run a HIBP check first.")
            return
        advice_prompt = (
            "The following data breach information has been found related to an account. "
            "Please act as a security advisor and provide detailed, actionable advice on what steps should be taken "
            "to mitigate risks. For each breach, consider the types of data compromised and suggest specific "
            "recommendations (e.g., changing passwords, monitoring accounts, enabling 2FA). "
            "\nData Breach Information:\n"
            f"{self.hibp_context_for_ai}"
        )

        self.tabs.setCurrentWidget(self.ai_advisor_tab)

        user_facing_message = "Requesting AI advice based on recent HIBP results..."
        escaped_user_message = self._js_escape(user_facing_message)
        self._run_chat_js(f"addUserMessage('{escaped_user_message}');")
        
        self._prepare_and_send_to_ollama(advice_prompt)

    def closeEvent(self, event):
        """
        Handles the window close event.
        Ensures the Ollama worker thread is properly stopped and cleaned up.
        """
        if self.ollama_worker and self.ollama_worker.isRunning():
            self.ollama_worker.stop() 
            self.ollama_worker.quit() 
            if not self.ollama_worker.wait(3000): 
                print("Ollama worker thread did not terminate via wait() in closeEvent.", file=sys.stderr)
                if self.ollama_worker: 
                    try:
                        self.ollama_worker.result.disconnect()
                        self.ollama_worker.finished_streaming.disconnect()
                        self.ollama_worker.error.disconnect()
                    except TypeError: 
                        pass
            # If wait() succeeds, we rely on the QThread.finished signal connected to _ollama_thread_terminated.
        super().closeEvent(event)