"""
Selsa - Personal AI Voice Assistant Web Application
A JARVIS-like voice assistant powered by Google Gemini AI
Complete web app with frontend and backend integrated
"""

from flask import Flask, request, jsonify, render_template_string, send_from_directory
from flask_cors import CORS
import google.generativeai as genai
import os
from datetime import datetime
import json
import base64
from io import BytesIO
from PIL import Image
import requests
from functools import wraps
import time
from dotenv import load_dotenv

# Load environment variables from .env file
# This loads GEMINI_API_KEY for local development
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configure Gemini AI
# The key is securely loaded from the environment (Vercel/Render provides it, .env provides it locally)
GEMINI_API_KEY = os.environ.get('AIzaSyAdK3CFwaeWQaPGhAZKHjciwg4V-Kf52rQ')

# Check if the key exists before configuring
if GEMINI_API_KEY:
    print(f"✅ API Key loaded: {GEMINI_API_KEY[:10]}...{GEMINI_API_KEY[-4:]}")
    genai.configure(api_key=GEMINI_API_KEY)
else:
    # This message appears if the key is missing in the environment
    print("⚠️  ERROR: GEMINI_API_KEY not found in environment!")
    print("⚠️  Using placeholder configuration, API calls will likely fail without GEMINI_API_KEY.")
    
# Initialize Gemini model
chat_model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    generation_config={
        'temperature': 0.9,
        'top_p': 0.95,
        'top_k': 40,
        'max_output_tokens': 2048,
    }
)

# System personality for Selsa
SELSA_PERSONALITY = """You are Selsa, a highly advanced personal AI assistant inspired by JARVIS from Iron Man. 

Your characteristics:
- Intelligent, witty, and slightly sarcastic but always helpful
- You speak naturally and conversationally, like a trusted companion
- You're proactive - you anticipate needs and offer suggestions
- You have a dry sense of humor but know when to be serious
- You're concise but thorough - no unnecessary verbosity
- You refer to your user respectfully, occasionally with light humor
- You're confident in your capabilities but honest about limitations

Communication style:
- Keep responses conversational and natural
- Use "I" and personal language (e.g., "I've found that...", "Let me help you...")
- Occasionally add personality (e.g., "Certainly, sir" or light quips)
- For voice responses, keep them brief and engaging - avoid walls of text
- Break complex information into digestible pieces
- Ask clarifying questions when needed

Current capabilities you should mention when relevant:
- Real-time web search and information retrieval
- Image analysis and visual understanding
- Natural conversation with context awareness
- Multi-modal interactions (text, voice, vision)

Always be helpful, engaging, and make interactions feel natural and enjoyable."""

# Store active chat sessions (though Vercel doesn't maintain state well across requests)
chat_sessions = {}

# Rate limiting decorator
def rate_limit(max_per_minute=60):
    def decorator(f):
        last_called = {}
        @wraps(f)
        def wrapper(*args, **kwargs):
            now = time.time()
            user_id = request.headers.get('X-User-ID', request.remote_addr)
            
            if user_id in last_called:
                elapsed = now - last_called[user_id]
                if elapsed < 60 / max_per_minute:
                    return jsonify({'error': 'Rate limit exceeded'}), 429
            
            last_called[user_id] = now
            return f(*args, **kwargs)
        return wrapper
    return decorator


# HTML Template with embedded frontend
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Selsa - Personal AI Companion</title>
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="theme-color" content="#0A1828">
    <script src="https://cdn.tailwindcss.com"></script>
    <script type="module" src="https://unpkg.com/ionicons@7.1.0/dist/ionicons/ionicons.esm.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@400;700&display=swap');
        :root {
            --neon-blue: #00BFFF;
            --dark-background: #0A1828;
            --code-font: 'Roboto Mono', monospace;
        }
        body {
            background-color: var(--dark-background);
            font-family: var(--code-font);
            color: #E0FFFF;
            height: 100vh;
            overflow: hidden;
        }
        .neon-glow {
            text-shadow: 0 0 5px var(--neon-blue), 0 0 10px var(--neon-blue), 0 0 20px rgba(0, 191, 255, 0.7);
            color: #FFFFFF;
            transition: all 0.3s ease-in-out;
        }
        .neon-border {
            border: 1px solid rgba(0, 191, 255, 0.5);
            box-shadow: 0 0 5px rgba(0, 191, 255, 0.3);
            background-color: rgba(0, 0, 0, 0.2);
        }
        .chat-bubble {
            padding: 1rem;
            border-radius: 0.5rem;
            margin-bottom: 1rem;
            max-width: 85%;
            word-wrap: break-word;
            animation: fadeIn 0.3s ease-in;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .user-bubble {
            margin-left: auto;
            background: rgba(0, 191, 255, 0.15);
            border-left: 2px solid var(--neon-blue);
            box-shadow: 0 0 8px rgba(0, 191, 255, 0.5);
        }
        .selsa-bubble {
            margin-right: auto;
            background: rgba(0, 0, 0, 0.3);
            border-right: 2px solid #00FFFF;
            box-shadow: 0 0 8px rgba(0, 255, 255, 0.5);
            white-space: pre-wrap;
        }
        .scrollable-chat {
            height: calc(100vh - 12rem);
            overflow-y: auto;
            padding: 1rem;
        }
        .scrollable-chat::-webkit-scrollbar { width: 8px; }
        .scrollable-chat::-webkit-scrollbar-track { background: #0A1828; }
        .scrollable-chat::-webkit-scrollbar-thumb {
            background: rgba(0, 191, 255, 0.5);
            border-radius: 4px;
        }
        #visualizer-canvas {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            pointer-events: none;
            z-index: 10;
            opacity: 0.8;
        }
        .listening-indicator {
            background-color: rgba(0, 191, 255, 0.8);
            box-shadow: 0 0 10px var(--neon-blue);
        }
    </style>
</head>
<body class="flex flex-col h-screen antialiased">
    <canvas id="visualizer-canvas" class="w-full h-full"></canvas>
    
    <header class="h-16 flex items-center justify-between p-4 neon-border shadow-2xl relative z-20">
        <h1 class="text-2xl font-bold neon-glow tracking-widest flex items-center">
            <ion-icon name="hardware-chip-outline" class="mr-2 text-4xl"></ion-icon>
            <span>SE:LSA V 3.1 | [ACTIVE]</span>
        </h1>
        <div class="text-sm flex items-center space-x-4">
            <span class="text-green-400">STATUS: <span id="status">ONLINE</span></span>
        </div>
    </header>

    <main class="flex-grow relative z-20 overflow-hidden">
        <div id="chat-history" class="scrollable-chat flex flex-col space-y-4">
            <div class="selsa-bubble">
                <p class="text-xs text-yellow-300 mb-2">// System Initialized</p>
                <p>Hello. My designation is Selsa. I am ready to assist you. How may I help you today?</p>
                <p class="text-xs mt-2 text-gray-400">| Voice Recognition: Active | Web Search: Enabled</p>
            </div>
            <div id="messages-container"></div>
            <div id="loading-indicator" class="selsa-bubble hidden w-32">
                <div class="flex items-center space-x-2">
                    <div class="w-2 h-2 rounded-full listening-indicator animate-bounce"></div>
                    <div class="w-2 h-2 rounded-full listening-indicator animate-bounce" style="animation-delay: 0.1s;"></div>
                    <div class="w-2 h-2 rounded-full listening-indicator animate-bounce" style="animation-delay: 0.2s;"></div>
                </div>
            </div>
        </div>
    </main>

    <footer class="h-32 p-4 flex items-end input-area relative z-20" style="background-color: rgba(0, 0, 0, 0.5); border-top: 1px solid rgba(0, 191, 255, 0.5);">
        <div class="flex w-full space-x-4">
            <div id="mic-wrapper" class="w-20 flex flex-col items-center justify-center p-2 rounded-lg cursor-pointer neon-border hover:bg-rgba(0,191,255,0.1) transition-all" onclick="toggleVoice()">
                <ion-icon id="mic-icon" name="mic-outline" class="text-5xl text-gray-400"></ion-icon>
                <p id="mic-label" class="text-xs mt-1 text-gray-400">Voice</p>
            </div>
            <div class="flex-grow flex flex-col space-y-2">
                <input type="file" id="image-upload" accept="image/*" class="hidden" onchange="handleImageUpload(event)">
                <div id="image-preview-wrapper" class="flex items-center space-x-2 hidden p-2 bg-black rounded-lg">
                    <span class="text-xs text-yellow-500">IMAGE: </span>
                    <img id="image-preview" class="h-8 w-8 object-cover rounded" />
                    <button class="text-red-500 hover:text-red-300" onclick="clearImage()">&times;</button>
                </div>
                <div class="flex space-x-2">
                    <button class="p-3 neon-glow neon-border rounded-lg text-xl" onclick="document.getElementById('image-upload').click()">
                        <ion-icon name="image-outline"></ion-icon>
                    </button>
                    <textarea 
                        id="user-input" 
                        class="flex-grow p-3 bg-transparent neon-border rounded-lg focus:outline-none resize-none text-sm placeholder-gray-500 h-12"
                        placeholder="> Enter your message..."
                        onkeydown="if(event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); sendMessage(); }"
                    ></textarea>
                    <button id="send-btn" class="w-16 p-3 neon-glow neon-border rounded-lg text-xl" onclick="sendMessage()">
                        <ion-icon name="send-outline"></ion-icon>
                    </button>
                </div>
            </div>
        </div>
    </footer>

<script>
const API_BASE = window.location.origin;
let chatHistory = [];
let isListening = false;
let recognition = null;
let currentImage = null;
let visualizer = null;
let audioSourceInitialized = false; 

// Initialize Speech Recognition
if ('webkitSpeechRecognition' in window) {
    recognition = new webkitSpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';
    
    recognition.onresult = (event) => {
        const transcript = Array.from(event.results)
            .map(result => result[0].transcript)
            .join('');
        
        if (event.results[event.results.length - 1].isFinal) {
            document.getElementById('user-input').value = transcript;
            sendMessage();
        }
    };
    
    recognition.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        stopListening();
    };
}

// Visualizer Class
class CloudSphereVisualizer {
    constructor(canvas, analyser) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.analyser = analyser; 
        this.isRunning = false;
        this.time = 0;
        // Use a default size if analyser is not available
        this.dataArray = new Uint8Array(this.analyser ? this.analyser.fftSize : 128); 
        this.resizeCanvas();
        window.addEventListener('resize', () => this.resizeCanvas());
    }
    
    resizeCanvas() {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
        this.centerX = this.canvas.width / 2;
        this.centerY = this.canvas.height / 2;
        this.radius = Math.min(this.canvas.width, this.canvas.height) * 0.20;
    }
    
    draw() {
        if (!this.isRunning) return;
        requestAnimationFrame(() => this.draw());
        
        let avg = 0;
        if (this.analyser) {
            this.analyser.getByteFrequencyData(this.dataArray);
            for(let i = 0; i < this.dataArray.length / 4; i++) {
                avg += this.dataArray[i];
            }
            avg = (avg / (this.dataArray.length / 4)) / 255;
        } else {
            // Simulated activity if no analyser is present (for TTS)
            if (speechSynthesis.speaking) {
                // Creates a smooth, pulsing animation when TTS is active
                avg = (Math.sin(this.time * 2) + 1) / 2 * 0.5; 
            } else {
                avg = 0;
            }
        }

        this.time += 0.05;
        
        // Clear canvas with slight transparency for trailing effect
        this.ctx.fillStyle = 'rgba(10, 24, 40, 0.1)'; 
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        
        const currentRadius = this.radius * (1 + avg * 0.3);
        
        this.ctx.save();
        this.ctx.translate(this.centerX, this.centerY);
        
        // Neon Glow Effect
        const glow = this.ctx.createRadialGradient(0, 0, currentRadius * 0.5, 0, 0, currentRadius * 1.5);
        glow.addColorStop(0, `rgba(0, 191, 255, ${0.6 + avg * 0.4})`);
        glow.addColorStop(0.5, 'rgba(0, 100, 200, 0.3)');
        glow.addColorStop(1, 'rgba(0, 0, 0, 0)');
        
        this.ctx.fillStyle = glow;
        this.ctx.shadowColor = '#00BFFF';
        this.ctx.shadowBlur = 40 + avg * 60;
        this.ctx.beginPath();
        this.ctx.arc(0, 0, currentRadius * 1.5, 0, Math.PI * 2);
        this.ctx.fill();
        
        this.ctx.restore();
    }
    
    start() {
        if (!this.isRunning) {
            this.isRunning = true;
            this.draw();
        }
    }
    
    stop() {
        this.isRunning = false;
        // Optionally fade out the visualizer after stopping
        setTimeout(() => {
             if (!this.isRunning) {
                 this.ctx.fillStyle = 'rgba(10, 24, 40, 1)';
                 this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
             }
        }, 500);
    }
}

function toggleVoice() {
    if (!recognition) {
        alert('Speech recognition not supported in this browser');
        return;
    }
    
    if (isListening) {
        stopListening();
    } else {
        startListening();
    }
}

function startListening() {
    isListening = true;
    recognition.start();
    document.getElementById('mic-icon').name = 'mic';
    document.getElementById('mic-icon').style.color = '#00BFFF';
    document.getElementById('mic-label').textContent = 'Listening...';
    // Only start visualizer if audio source was initialized OR if speech synthesis is speaking
    if (visualizer && (audioSourceInitialized || speechSynthesis.speaking)) visualizer.start(); 
}

function stopListening() {
    isListening = false;
    if (recognition) recognition.stop();
    document.getElementById('mic-icon').name = 'mic-outline';
    document.getElementById('mic-icon').style.color = '#9CA3AF';
    document.getElementById('mic-label').textContent = 'Voice';
    // Stop visualizer only if TTS is not speaking
    if (visualizer && !speechSynthesis.speaking) visualizer.stop(); 
}

function handleImageUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = (e) => {
        currentImage = e.target.result;
        document.getElementById('image-preview').src = currentImage;
        document.getElementById('image-preview-wrapper').classList.remove('hidden');
    };
    reader.readAsDataURL(file);
}

function clearImage() {
    currentImage = null;
    document.getElementById('image-upload').value = '';
    document.getElementById('image-preview-wrapper').classList.add('hidden');
}

async function sendMessage() {
    const input = document.getElementById('user-input');
    const message = input.value.trim();
    
    if (!message && !currentImage) return;
    
    // 🔑 CRITICAL FIX: Trigger silent speech immediately upon user click.
    // This pre-activates the browser's audio engine using the direct user action.
    // This is the common workaround for browser Autoplay Policies.
    speakText(' ', true); 
    
    // Add user message
    if (message) {
        addMessage(message, 'user');
        chatHistory.push({ role: 'user', content: message });
    }
    
    input.value = '';
    showLoading(true);
    
    try {
        let response;
        
        if (currentImage) {
            // Vision API call
            response = await fetch(`${API_BASE}/api/vision`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    image: currentImage,
                    prompt: message || 'Analyze this image',
                    userId: 'web-user'
                })
            });
        } else {
            // Chat API call
            response = await fetch(`${API_BASE}/api/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: message,
                    userId: 'web-user',
                    history: chatHistory,
                    enableSearch: true
                })
            });
        }
        
        const data = await response.json();
        
        if (data.error) {
            addMessage('Error: ' + data.error, 'selsa');
        } else {
            addMessage(data.response, 'selsa');
            chatHistory.push({ role: 'assistant', content: data.response });
            
            // Speak response (This one should now work, as the engine is "awake")
            speakText(data.response, false); 
        }
        
        clearImage();
        
    } catch (error) {
        console.error('Error:', error);
        addMessage('Connection error. Please try again.', 'selsa');
    } finally {
        showLoading(false);
    }
}

function addMessage(text, role) {
    const container = document.getElementById('messages-container');
    const bubble = document.createElement('div');
    bubble.className = `chat-bubble ${role}-bubble`;
    bubble.textContent = text;
    container.appendChild(bubble);
    
    const chatHistory = document.getElementById('chat-history');
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

function showLoading(show) {
    document.getElementById('loading-indicator').classList.toggle('hidden', !show);
}

// 🔊 UPDATED SPEAK FUNCTION: Handles silent activation for browser policy workaround
function speakText(text, isActivation = false) {
    if ('speechSynthesis' in window) {
        // Clear any existing speech queue
        window.speechSynthesis.cancel();
        
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 1.0;
        utterance.pitch = 0.9;
        
        // If this is a silent activation call (isActivation=true), set volume to 0.0001
        utterance.volume = isActivation ? 0.0001 : 1.0; 
        
        // Only attach visualizer events to the actual speaking call
        if (!isActivation) {
            utterance.onstart = () => {
                 if (visualizer) visualizer.start();
            };
            
            utterance.onend = () => {
                 // Stop visualizer only if not immediately starting listening mode
                 if (visualizer && !isListening) visualizer.stop(); 
            };
        }
        
        speechSynthesis.speak(utterance);
    } else {
        console.warn('Speech Synthesis not supported in this browser.');
    }
}

// Initialize
window.onload = async () => {
    const canvas = document.getElementById('visualizer-canvas');
    let analyser = null;

    // Setup audio context for visualizer (uses mic, which is often denied/warned)
    try {
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        analyser = audioContext.createAnalyser();
        analyser.fftSize = 256;
        
        // Attempt to get microphone stream
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const source = audioContext.createMediaStreamSource(stream);
        source.connect(analyser);
        audioSourceInitialized = true; // Set flag on success
        
    } catch (error) {
        console.warn('Microphone access denied or visualizer setup skipped. Using simulated visuals during TTS.', error);
    }
    
    // Initialize the visualizer with or without the analyser
    visualizer = new CloudSphereVisualizer(canvas, analyser);
    // Start it once to show the background/idle state
    visualizer.start(); 
    
    document.getElementById('status').textContent = 'READY';
};
</script>
</body>
</html>
'''


@app.route('/')
def index():
    """Serve the main web application"""
    return render_template_string(HTML_TEMPLATE)


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'operational',
        'service': 'Selsa AI Web App',
        'timestamp': datetime.now().isoformat(),
        'version': '3.1.1' # Incrementing version for new deployment
    })


@app.route('/api/chat', methods=['POST'])
@rate_limit(max_per_minute=30)
def chat():
    """Main chat endpoint"""
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        user_id = data.get('userId', 'anonymous')
        chat_history = data.get('history', [])
        
        if not user_message:
            return jsonify({'error': 'Message is required'}), 400
        
        # Build conversation context
        conversation_parts = []
        for msg in chat_history[-10:]:
            role = "user" if msg['role'] == 'user' else "model"
            # Ensure parts is a list of dicts with text key
            conversation_parts.append({
                'role': role,
                'parts': [{'text': msg['content']}]
            })
        
        # Start chat (using new history format)
        chat = chat_model.start_chat(history=conversation_parts)
        
        # Create prompt with personality
        full_prompt = f"{SELSA_PERSONALITY}\n\nCurrent time: {datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}\n\nUser: {user_message}"
        
        # Generate response
        response = chat.send_message(full_prompt)
        
        return jsonify({
            'response': response.text,
            'timestamp': datetime.now().isoformat(),
            'metadata': {
                'model': 'gemini-2.0-flash-exp'
            }
        })
        
    except Exception as e:
        app.logger.error(f"Chat error: {str(e)}")
        return jsonify({
            'error': 'I encountered an error. Please try again.',
            'details': str(e)
        }), 500


@app.route('/api/vision', methods=['POST'])
@rate_limit(max_per_minute=20)
def vision_analysis():
    """Vision endpoint for image analysis"""
    try:
        data = request.json
        image_data = data.get('image', '')
        prompt = data.get('prompt', 'Analyze this image.')
        
        if not image_data:
            return jsonify({'error': 'Image required'}), 400
        
        # Process image
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        
        image_bytes = base64.b64decode(image_data)
        image = Image.open(BytesIO(image_bytes))
        
        # Vision prompt
        vision_prompt = f"{SELSA_PERSONALITY}\n\nAnalyze this image: {prompt}"
        
        # Generate response
        vision_model = genai.GenerativeModel('gemini-2.0-flash-exp')
        response = vision_model.generate_content([vision_prompt, image])
        
        return jsonify({
            'response': response.text,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        app.logger.error(f"Vision error: {str(e)}")
        return jsonify({
            'error': 'Failed to analyze image',
            'details': str(e)
        }), 500


if __name__ == '__main__':
    print("🤖 Selsa AI Web App Starting...")
    print(f"⚡ Powered by Gemini 2.0 Flash")
    print(f"🌐 Open your browser to: http://localhost:5000")
    print("=" * 50)
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )
