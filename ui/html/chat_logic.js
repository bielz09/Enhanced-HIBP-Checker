// chat_logic.js
// This script handles the client-side logic for the AI Advisor chat interface.
// It is loaded by chat_template.html and interacts with the PyQt6 application (MainWindow.py)
// through JavaScript calls initiated from Python (e.g., ai_chat_view.page().runJavaScript(...)).

// Functions in this script are responsible for:
// - Adding user, AI, and system messages to the chat display.
// - Sanitizing message content to prevent XSS, primarily using DOMPurify if available.
// - Managing the display of a "thinking" indicator for AI responses.
// - Scrolling the chat view to the latest message.

const messageContainer = document.getElementById('message-container');
let currentAIMessageElement = null; 
let currentAIMessageId = null;

function sanitizeHTML(text) {
    // Basic HTML sanitizer: converts text to its HTML entity equivalent.
    // Used as a fallback if DOMPurify is not available or for simple text.
    const temp = document.createElement('div');
    temp.textContent = text;
    return temp.innerHTML;
}

function addMessage(text, type, messageId = null) {
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', `${type}-message`);
    
    if (type === 'ai' && messageId) {
        messageDiv.id = messageId;
    }

    // Text is raw here; will be sanitized before insertion into innerHTML.
    let sanitizedText = text;

    if (type === 'user') {
        messageDiv.innerHTML = "<b>You:</b><br>" + sanitizeHTML(text); // User text is sanitized
    } else if (type === 'ai') {
        const aiPrefix = "<b>AI:</b><br>";
        if (text.includes('class="thinking-indicator"') || text.includes("class='thinking-indicator'")) {
            messageDiv.innerHTML = aiPrefix + text; // Thinking indicator is pre-formatted and trusted (generated internally)
        } else {
            let processedText = text.replace(/^[\u200B\u200C\u200D\u200E\u200F\uFEFF]/,""); // Remove leading zero-width spaces
            let htmlOutput;
            // Prefer DOMPurify for robust HTML sanitization if it's loaded.
            // The AI is instructed to send plain text, but this is a defense-in-depth measure.
            if (typeof DOMPurify !== 'undefined') {
                htmlOutput = DOMPurify.sanitize(processedText.replace(/\n/g, '<br>'));
            } else {
                // Fallback sanitizer if DOMPurify fails to load.
                htmlOutput = sanitizeHTML(processedText); // sanitizeHTML will escape HTML chars; CSS handles newlines via pre-line.
            }
            messageDiv.innerHTML = aiPrefix + htmlOutput;
        }
    } else { // system
        messageDiv.textContent = text; // System messages are plain text
    }
    
    messageContainer.appendChild(messageDiv);
    scrollToBottom();
    return messageDiv;
}

function addUserMessage(text) {
    addMessage(text, 'user');
}

function addSystemMessage(text) {
    addMessage(text, 'system');
}

function startAIMessage(thinkingText = "Thinking...") {
    currentAIMessageId = "ai-message-" + Date.now();
    // MODIFIED HTML structure for the thinking indicator
    const thinkingHTML = "<span class='thinking-indicator'>" + sanitizeHTML(thinkingText) + "</span>";
    currentAIMessageElement = addMessage(thinkingHTML, 'ai', currentAIMessageId);
    return currentAIMessageId;
}

function updateAIMessageContent(messageId, newContent) {
     const el = document.getElementById(messageId);
     if (el) {
        let processedNewContent = newContent.replace(/^[\u200B\u200C\u200D\u200E\u200F\uFEFF]/,""); // Remove leading zero-width spaces
        let htmlOutput;
        // Prefer DOMPurify for robust HTML sanitization.
        if (typeof DOMPurify !== 'undefined') {
            htmlOutput = DOMPurify.sanitize(processedNewContent.replace(/\n/g, '<br>'));
        } else {
            // Fallback sanitizer.
            htmlOutput = sanitizeHTML(processedNewContent);
        }
        el.innerHTML = "<b>AI:</b><br>" + htmlOutput;
        scrollToBottom();
     }
}

function scrollToBottom() {
     messageContainer.scrollTop = messageContainer.scrollHeight;
}