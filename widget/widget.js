(function () {
  'use strict';

  // =========================================================================
  // CONFIGURATION: BACKEND URL
  // Set to local FastAPI dev server or deployed endpoint
  // =========================================================================
  const MINDBRIDGE_BACKEND_URL = (() => {
    const host = typeof window !== 'undefined' ? window.location.hostname : '';
    // Local development
    if (host === '127.0.0.1' || host === 'localhost') {
      return 'http://127.0.0.1:8001';
    }
    // Production: Render-deployed API
    return 'https://mindbridge-api.onrender.com';
  })();

  const STORAGE_KEY_SESSION = 'mindbridge_session_id';
  const STORAGE_KEY_HISTORY = 'mindbridge_chat_history';

  // Ellen Avatar Image Path
  const currentScript = (typeof document !== 'undefined' && (document.currentScript || document.getElementById('mindbridge-widget-script'))) || null;
  const SCRIPT_BASE_URL = currentScript && currentScript.src ? currentScript.src.substring(0, currentScript.src.lastIndexOf('/')) : '';
  const ELLEN_AVATAR_URL = SCRIPT_BASE_URL ? `${SCRIPT_BASE_URL}/ellen_avatar.jpg` : 'ellen_avatar.jpg';

  // 3 Quick Starter Options (displayed horizontally like the reference image)
  const STARTER_OPTIONS = [
    {
      id: 'opt-therapist',
      icon: `<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="#2563EB" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>`,
      title: 'Help me find the right therapist',
      prompt: 'Help me find the right therapist'
    },
    {
      id: 'opt-consultation',
      icon: `<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="#7C3AED" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="3" ry="3"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>`,
      title: "I'd like to book a consultation",
      prompt: "I'd like to book a consultation"
    },
    {
      id: 'opt-begin',
      icon: `<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="#059669" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"></polygon></svg>`,
      title: "I'm not sure where to begin",
      prompt: "I'm not sure where to begin"
    }
  ];

  // Inject Google Fonts preconnect & stylesheet for Plus Jakarta Sans & Outfit
  if (typeof document !== 'undefined' && !document.getElementById('mindbridge-font-link')) {
    const preconnect1 = document.createElement('link');
    preconnect1.rel = 'preconnect';
    preconnect1.href = 'https://fonts.googleapis.com';
    document.head.appendChild(preconnect1);

    const preconnect2 = document.createElement('link');
    preconnect2.rel = 'preconnect';
    preconnect2.href = 'https://fonts.gstatic.com';
    preconnect2.crossOrigin = 'anonymous';
    document.head.appendChild(preconnect2);

    const fontLink = document.createElement('link');
    fontLink.id = 'mindbridge-font-link';
    fontLink.rel = 'stylesheet';
    fontLink.href = 'https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Outfit:wght@500;600;700&display=swap';
    document.head.appendChild(fontLink);
  }

  // Inject Widget Stylesheet
  const style = document.createElement('style');
  style.id = 'mindbridge-widget-styles';
  style.textContent = `
    #mindbridge-widget-container,
    #mindbridge-widget-container * {
      box-sizing: border-box;
    }

    #mindbridge-widget-container {
      font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      position: fixed;
      bottom: 24px;
      right: 24px;
      z-index: 999999;
      color: #0F172A;
      line-height: 1.55;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
    }

    /* Floating Launcher Button with Ellen's Realistic Photo */
    #mindbridge-launcher-btn {
      width: 66px;
      height: 66px;
      border-radius: 50%;
      background: linear-gradient(135deg, #2563EB 0%, #7C3AED 50%, #EC4899 100%);
      padding: 3px;
      border: none;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 10px 28px rgba(37, 99, 235, 0.38), 0 4px 10px rgba(15, 23, 42, 0.08);
      transition: transform 0.24s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.24s ease;
      outline: none;
      position: relative;
    }

    #mindbridge-launcher-btn:hover {
      transform: translateY(-3px) scale(1.06);
      box-shadow: 0 14px 36px rgba(37, 99, 235, 0.48), 0 6px 14px rgba(15, 23, 42, 0.12);
    }

    #mindbridge-launcher-btn:active {
      transform: scale(0.95);
    }

    .mindbridge-launcher-avatar-img {
      width: 100%;
      height: 100%;
      border-radius: 50%;
      object-fit: cover;
      object-position: center 15%;
      display: block;
      border: 2px solid #FFFFFF;
      background: #E2E8F0;
    }

    .mindbridge-launcher-beacon {
      position: absolute;
      bottom: 2px;
      right: 2px;
      width: 15px;
      height: 15px;
      border-radius: 50%;
      background: #10B981;
      border: 2.5px solid #FFFFFF;
      box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.3);
      z-index: 2;
      animation: mindbridgeDotPulse 3s ease-in-out infinite;
    }

    @keyframes mindbridgeDotPulse {
      0%, 100% {
        box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.3);
      }
      50% {
        box-shadow: 0 0 0 5px rgba(16, 185, 129, 0.5);
      }
    }

    /* =========================================================================
       CHAT WINDOW CONTAINER (Full Height on Laptop/Desktop Screens)
       ========================================================================= */
    #mindbridge-chat-window {
      display: none;
      position: absolute;
      bottom: 0px;
      right: 0;
      width: 420px;
      height: calc(100vh - 40px);
      max-height: calc(100vh - 40px);
      background: linear-gradient(135deg, #FAFBFD 0%, #EEF4FF 25%, #F5F3FF 50%, #FFF7ED 75%, #F0FDF4 100%);
      background-size: 300% 300%;
      animation: mindbridgeBgFlow 18s ease-in-out infinite alternate, mindbridgeFadeSlide 0.26s cubic-bezier(0.16, 1, 0.3, 1);
      border-radius: 28px;
      box-shadow: 0 24px 54px -10px rgba(15, 23, 42, 0.18), 0 10px 24px -6px rgba(15, 23, 42, 0.08), 0 0 0 1px rgba(255, 255, 255, 0.8) inset, 0 0 0 1px rgba(226, 232, 240, 0.85);
      flex-direction: column;
      overflow: hidden;
      position: relative;
    }

    @keyframes mindbridgeBgFlow {
      0% {
        background-position: 0% 30%;
      }
      50% {
        background-position: 100% 70%;
      }
      100% {
        background-position: 0% 30%;
      }
    }

    @keyframes mindbridgeFadeSlide {
      from {
        opacity: 0;
        transform: translateY(16px) scale(0.97);
      }
      to {
        opacity: 1;
        transform: translateY(0) scale(1);
      }
    }

    /* Header Bar */
    #mindbridge-chat-header {
      position: relative;
      z-index: 10;
      background: rgba(255, 255, 255, 0.84);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      padding: 14px 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid rgba(226, 232, 240, 0.75);
    }

    .mindbridge-header-profile {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .mindbridge-avatar-wrap {
      position: relative;
      width: 42px;
      height: 42px;
      border-radius: 50%;
      background: linear-gradient(135deg, #2563EB 0%, #7C3AED 50%, #EC4899 100%);
      padding: 2px;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 2px 10px rgba(37, 99, 235, 0.16);
      flex-shrink: 0;
    }

    .mindbridge-header-avatar-img {
      width: 100%;
      height: 100%;
      border-radius: 50%;
      object-fit: cover;
      object-position: center 15%;
      display: block;
      border: 1.5px solid #FFFFFF;
      background: #E2E8F0;
    }

    .mindbridge-status-dot {
      position: absolute;
      bottom: 0px;
      right: 0px;
      width: 11px;
      height: 11px;
      border-radius: 50%;
      background-color: #10B981;
      border: 2px solid #FFFFFF;
      box-shadow: 0 0 0 1px rgba(16, 185, 129, 0.3);
    }

    .mindbridge-header-info {
      display: flex;
      flex-direction: column;
      gap: 1px;
    }

    .mindbridge-header-title {
      font-size: 15px;
      font-weight: 700;
      color: #0F172A;
      letter-spacing: -0.2px;
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .mindbridge-header-subtitle {
      font-size: 11.5px;
      font-weight: 500;
      color: #64748B;
    }

    .mindbridge-header-actions {
      display: flex;
      align-items: center;
      gap: 4px;
    }

    .mindbridge-icon-btn {
      background: transparent;
      border: none;
      color: #64748B;
      cursor: pointer;
      width: 32px;
      height: 32px;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 50%;
      transition: background-color 0.18s, color 0.18s, transform 0.15s;
    }

    .mindbridge-icon-btn:hover {
      background-color: rgba(15, 23, 42, 0.06);
      color: #0F172A;
      transform: scale(1.05);
    }

    .mindbridge-icon-btn:active {
      transform: scale(0.95);
    }

    /* Dynamic Content Container */
    #mindbridge-content-area {
      flex: 1;
      position: relative;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }

    /* =========================================================================
       WELCOME VIEW: CENTRAL AURA ORB & 3 ACTION CARDS (Like Reference Image)
       ========================================================================= */
    #mindbridge-welcome-view {
      flex: 1;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      padding: 20px 18px 16px 18px;
      overflow-y: auto;
      position: relative;
      z-index: 2;
      animation: mindbridgeFadeIn 0.3s ease-out;
    }

    /* Central Ethereal Living Aura Orb */
    .mindbridge-aura-stage {
      flex: 1;
      position: relative;
      width: 100%;
      min-height: 220px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
    }

    .mindbridge-aura-canvas {
      position: absolute;
      width: 200px;
      height: 200px;
      display: flex;
      align-items: center;
      justify-content: center;
      pointer-events: none;
    }

    .mindbridge-aura-glow {
      position: absolute;
      width: 180px;
      height: 180px;
      border-radius: 50%;
      background: radial-gradient(circle at 45% 45%, #93C5FD 0%, #C4B5FD 35%, #FBCFE8 65%, #FDE68A 100%);
      filter: blur(46px);
      opacity: 0.88;
      animation: mindbridgeAuraBreath 8s ease-in-out infinite alternate, mindbridgeAuraSpin 22s linear infinite;
      will-change: transform, filter;
    }

    .mindbridge-aura-core {
      position: absolute;
      width: 150px;
      height: 150px;
      border-radius: 50%;
      background: radial-gradient(circle at 55% 55%, #BAE6FD 0%, #DDD6FE 45%, #FCE7F3 85%);
      filter: blur(34px);
      opacity: 0.72;
      animation: mindbridgeAuraBreath 10s ease-in-out infinite alternate-reverse;
      will-change: transform;
    }

    /* Welcoming Hero Text over Aura */
    .mindbridge-welcome-hero {
      position: relative;
      z-index: 5;
      text-align: center;
      padding: 0 14px;
      pointer-events: none;
      user-select: none;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      animation: mindbridgeFadeIn 0.35s ease-out;
    }

    .mindbridge-welcome-salutation {
      font-size: 15px;
      font-weight: 600;
      color: #64748B;
      letter-spacing: -0.2px;
      margin-bottom: 3px;
    }

    .mindbridge-welcome-headline {
      font-size: 23px;
      font-weight: 700;
      color: #0F172A;
      letter-spacing: -0.5px;
      line-height: 1.35;
      font-family: 'Outfit', 'Plus Jakarta Sans', sans-serif;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: center;
      gap: 6px;
    }

    .mindbridge-static-phrase {
      color: #0F172A;
    }

    .mindbridge-ticker-slot {
      display: inline-flex;
      position: relative;
      align-items: center;
      justify-content: center;
      min-width: 65px;
      height: 32px;
      overflow: hidden;
      vertical-align: middle;
    }

    .mindbridge-ticker-word {
      display: inline-block;
      background: linear-gradient(135deg, #2563EB 0%, #7C3AED 50%, #EC4899 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      font-weight: 800;
      letter-spacing: -0.3px;
      transition: transform 0.36s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.36s ease, filter 0.36s ease;
      will-change: transform, opacity, filter;
    }

    .mindbridge-ticker-word.ticker-slide-out {
      transform: translateY(-16px);
      opacity: 0;
      filter: blur(4px);
    }

    .mindbridge-ticker-word.ticker-slide-in {
      transform: translateY(16px);
      opacity: 0;
      filter: blur(4px);
    }

    @keyframes mindbridgeAuraBreath {
      0% {
        transform: scale(0.9) translate3d(0, 0, 0);
      }
      50% {
        transform: scale(1.14) translate3d(8px, -8px, 0);
      }
      100% {
        transform: scale(0.95) translate3d(-6px, 6px, 0);
      }
    }

    @keyframes mindbridgeAuraSpin {
      0% {
        transform: rotate(0deg);
      }
      100% {
        transform: rotate(360deg);
      }
    }

    /* 3 Action Starter Cards in a Row (exactly like the reference image) */
    .mindbridge-starter-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 10px;
      margin-top: auto;
      margin-bottom: 4px;
    }

    .mindbridge-starter-card {
      background: rgba(255, 255, 255, 0.92);
      backdrop-filter: blur(14px);
      -webkit-backdrop-filter: blur(14px);
      border: 1px solid rgba(226, 232, 240, 0.9);
      border-radius: 16px;
      padding: 14px 10px;
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      justify-content: space-between;
      min-height: 98px;
      cursor: pointer;
      box-shadow: 0 3px 10px rgba(15, 23, 42, 0.03), 0 1px 2px rgba(15, 23, 42, 0.02);
      transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.2s ease, border-color 0.2s ease, background-color 0.2s ease;
      text-align: left;
      outline: none;
    }

    .mindbridge-starter-card:hover {
      transform: translateY(-3px);
      background: #FFFFFF;
      border-color: #93C5FD;
      box-shadow: 0 8px 20px rgba(37, 99, 235, 0.12), 0 2px 6px rgba(15, 23, 42, 0.04);
    }

    .mindbridge-starter-card:active {
      transform: scale(0.97);
    }

    .mindbridge-starter-icon {
      width: 28px;
      height: 28px;
      display: flex;
      align-items: center;
      justify-content: flex-start;
      margin-bottom: 10px;
    }

    .mindbridge-starter-title {
      font-size: 12px;
      font-weight: 600;
      color: #1E293B;
      line-height: 1.35;
      letter-spacing: -0.1px;
    }

    /* =========================================================================
       ACTIVE MESSAGE LIST & GEMINI-STYLE CHAT BUBBLES
       ========================================================================= */
    #mindbridge-message-list {
      display: none;
      flex: 1;
      padding: 20px 18px 20px 18px;
      overflow-y: auto;
      flex-direction: column;
      gap: 16px;
      scroll-behavior: smooth;
      position: relative;
      z-index: 2;
    }

    #mindbridge-widget-container .mindbridge-message {
      font-size: 14.5px;
      line-height: 1.62;
      word-break: break-word;
      animation: mindbridgeFadeIn 0.24s cubic-bezier(0.16, 1, 0.3, 1);
      position: relative;
      margin: 0;
    }

    /* Receiving Message (Assistant / Ellen) - Crisp Pure White Card with Generous Padding */
    #mindbridge-widget-container .mindbridge-message.assistant {
      align-self: flex-start;
      max-width: 86%;
      background-color: #FFFFFF !important;
      color: #0F172A !important;
      border: 1px solid rgba(226, 232, 240, 0.9);
      border-radius: 20px 20px 20px 4px;
      padding: 16px 20px !important;
      box-shadow: 0 4px 16px rgba(15, 23, 42, 0.05), 0 1px 3px rgba(15, 23, 42, 0.02);
      white-space: normal;
    }

    #mindbridge-widget-container .mindbridge-message.assistant p {
      margin: 0 0 8px 0;
      line-height: 1.62;
    }

    #mindbridge-widget-container .mindbridge-message.assistant p:last-child {
      margin-bottom: 0;
    }

    #mindbridge-widget-container .mindbridge-message.assistant ul,
    #mindbridge-widget-container .mindbridge-message.assistant ol {
      margin: 8px 0 8px 20px;
      padding: 0;
      line-height: 1.6;
    }

    #mindbridge-widget-container .mindbridge-message.assistant li {
      margin-bottom: 5px;
    }

    #mindbridge-widget-container .mindbridge-message.assistant li:last-child {
      margin-bottom: 0;
    }

    #mindbridge-widget-container .mindbridge-message.assistant strong,
    #mindbridge-widget-container .mindbridge-message.assistant b {
      font-weight: 600;
      color: #0F172A;
    }

    /* Sender Message (User) - Vibrant Blue Gemini Bubble with Generous Padding */
    #mindbridge-widget-container .mindbridge-message.user {
      align-self: flex-end;
      max-width: 82%;
      background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%);
      color: #FFFFFF !important;
      border-radius: 20px 20px 4px 20px;
      padding: 14px 20px !important;
      box-shadow: 0 5px 18px rgba(37, 99, 235, 0.28);
      white-space: pre-wrap;
      letter-spacing: -0.1px;
    }

    /* Error Message */
    #mindbridge-widget-container .mindbridge-message.error {
      align-self: center;
      background-color: #FEF2F2;
      color: #991B1B;
      border: 1px solid #FCA5A5;
      font-size: 12.5px;
      border-radius: 14px;
      text-align: center;
      padding: 12px 16px !important;
      max-width: 90%;
      line-height: 1.5;
    }

    /* Typing Indicator with Pulsing Gradient Orbs */
    #mindbridge-widget-container .mindbridge-typing-indicator {
      align-self: flex-start;
      background: #FFFFFF;
      padding: 12px 18px !important;
      border-radius: 20px 20px 20px 4px;
      display: inline-flex;
      align-items: center;
      gap: 7px;
      border: 1px solid rgba(226, 232, 240, 0.88);
      box-shadow: 0 3px 10px rgba(15, 23, 42, 0.04);
      animation: mindbridgeFadeIn 0.2s ease-out;
    }

    .mindbridge-typing-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: linear-gradient(135deg, #2563EB 0%, #7C3AED 50%, #EC4899 100%);
      background-size: 200% 200%;
      animation: mindbridgeGradientPulse 1.4s ease-in-out infinite;
    }

    .mindbridge-typing-dot:nth-child(1) { animation-delay: 0s; }
    .mindbridge-typing-dot:nth-child(2) { animation-delay: 0.18s; }
    .mindbridge-typing-dot:nth-child(3) { animation-delay: 0.36s; }

    @keyframes mindbridgeGradientPulse {
      0%, 100% {
        transform: scale(0.8);
        opacity: 0.45;
        background-position: 0% 50%;
      }
      50% {
        transform: scale(1.25);
        opacity: 1;
        background-position: 100% 50%;
      }
    }

    @keyframes mindbridgeFadeIn {
      from { opacity: 0; transform: translateY(6px); }
      to { opacity: 1; transform: translateY(0); }
    }

    /* =========================================================================
       FOOTER & INPUT BAR (Gemini-style Pill with Aura Pip)
       ========================================================================= */
    #mindbridge-chat-footer {
      padding: 12px 18px 16px 18px;
      background: rgba(255, 255, 255, 0.9);
      backdrop-filter: blur(14px);
      -webkit-backdrop-filter: blur(14px);
      border-top: 1px solid rgba(226, 232, 240, 0.75);
      position: relative;
      z-index: 10;
    }

    .mindbridge-input-wrapper {
      display: flex;
      align-items: center;
      background: #FFFFFF;
      border: 1.5px solid #E2E8F0;
      border-radius: 28px;
      padding: 4px 6px 4px 14px;
      box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
      transition: border-color 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease;
      gap: 8px;
    }

    .mindbridge-input-wrapper:focus-within {
      background: #FFFFFF;
      border-color: #2563EB;
      box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12), 0 4px 14px rgba(37, 99, 235, 0.08);
    }

    /* Miniature Glowing Aura Icon inside input pill like reference image */
    .mindbridge-input-aura-pip {
      width: 16px;
      height: 16px;
      border-radius: 50%;
      background: radial-gradient(circle, #93C5FD 0%, #C4B5FD 50%, #FBCFE8 100%);
      flex-shrink: 0;
      box-shadow: 0 0 8px rgba(147, 197, 253, 0.6);
    }

    #mindbridge-input-field {
      flex: 1;
      padding: 9px 2px;
      font-size: 14px;
      border: none;
      background: transparent;
      outline: none;
      color: #0F172A;
      font-family: inherit;
    }

    #mindbridge-input-field::placeholder {
      color: #94A3B8;
      font-size: 13.5px;
    }

    #mindbridge-send-btn {
      background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%);
      color: #FFFFFF;
      border: none;
      width: 36px;
      height: 36px;
      border-radius: 50%;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: transform 0.18s ease, opacity 0.18s ease, box-shadow 0.18s ease;
      flex-shrink: 0;
      box-shadow: 0 3px 8px rgba(37, 99, 235, 0.32);
    }

    #mindbridge-send-btn:hover:not(:disabled) {
      transform: scale(1.06);
      box-shadow: 0 5px 14px rgba(37, 99, 235, 0.42);
    }

    #mindbridge-send-btn:active:not(:disabled) {
      transform: scale(0.92);
    }

    #mindbridge-send-btn:disabled {
      background: #CBD5E1;
      box-shadow: none;
      cursor: not-allowed;
      opacity: 0.75;
      transform: none;
    }

    /* Mobile Responsive View */
    @media (max-width: 540px) {
      #mindbridge-widget-container {
        position: static !important;
      }
      #mindbridge-chat-window {
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        right: 0 !important;
        bottom: 0 !important;
        width: 100vw !important;
        height: 100vh !important;
        max-height: 100vh !important;
        border-radius: 0 !important;
        border: none !important;
        box-shadow: none !important;
        z-index: 999999 !important;
      }
    }
  `;
  document.head.appendChild(style);

  // Inject Widget DOM Elements
  const container = document.createElement('div');
  container.id = 'mindbridge-widget-container';
  container.innerHTML = `
    <!-- Floating Launcher Button with Ellen's Photo -->
    <button id="mindbridge-launcher-btn" aria-label="Chat with Ellen - MindBridge AI Assistant">
      <img src="${ELLEN_AVATAR_URL}" alt="Ellen - MindBridge AI Assistant" class="mindbridge-launcher-avatar-img" />
      <span class="mindbridge-launcher-beacon" title="Online"></span>
    </button>

    <!-- Chat Window -->
    <div id="mindbridge-chat-window" role="dialog" aria-modal="true" aria-labelledby="mindbridge-chat-title">
      <!-- Header -->
      <div id="mindbridge-chat-header">
        <div class="mindbridge-header-profile">
          <div class="mindbridge-avatar-wrap">
            <img src="${ELLEN_AVATAR_URL}" alt="Ellen" class="mindbridge-header-avatar-img" />
            <span class="mindbridge-status-dot" title="Online"></span>
          </div>
          <div class="mindbridge-header-info">
            <div id="mindbridge-chat-title" class="mindbridge-header-title">Ellen</div>
            <div class="mindbridge-header-subtitle">MindBridge AI Assistant</div>
          </div>
        </div>

        <div class="mindbridge-header-actions">
          <button id="mindbridge-reset-btn" class="mindbridge-icon-btn" title="Start New Chat" aria-label="Start New Chat">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"></path>
              <path d="M21 3v5h-5"></path>
              <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"></path>
              <path d="M3 21v-5h5"></path>
            </svg>
          </button>
          <button id="mindbridge-close-btn" class="mindbridge-icon-btn" title="Close Chat" aria-label="Close Chat">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
      </div>

      <!-- Main Dynamic Content Area -->
      <div id="mindbridge-content-area">
        <!-- Initial Welcome View with Ethereal Aura & 3 Starter Cards -->
        <div id="mindbridge-welcome-view">
          <div class="mindbridge-aura-stage">
            <div class="mindbridge-aura-canvas">
              <div class="mindbridge-aura-glow"></div>
              <div class="mindbridge-aura-core"></div>
            </div>

            <!-- Welcoming Greeting & Creative Word Ticker in the Middle -->
            <div class="mindbridge-welcome-hero">
              <div class="mindbridge-welcome-salutation">Hi there,</div>
              <div class="mindbridge-welcome-headline">
                <span class="mindbridge-static-phrase">let us help you</span>
                <span class="mindbridge-ticker-slot">
                  <span id="mindbridge-ticker-text" class="mindbridge-ticker-word">heal.</span>
                </span>
              </div>
            </div>
          </div>

          <!-- 3 Starter Option Cards (in a row like reference image) -->
          <div class="mindbridge-starter-grid" id="mindbridge-starter-list">
            ${STARTER_OPTIONS.map(
              (opt) => `
              <button class="mindbridge-starter-card" data-prompt="${opt.prompt}" id="${opt.id}">
                <div class="mindbridge-starter-icon">
                  ${opt.icon}
                </div>
                <div class="mindbridge-starter-title">${opt.title}</div>
              </button>
            `
            ).join('')}
          </div>
        </div>

        <!-- Active Message List -->
        <div id="mindbridge-message-list"></div>
      </div>

      <!-- Input Area -->
      <form id="mindbridge-chat-footer">
        <div class="mindbridge-input-wrapper">
          <div class="mindbridge-input-aura-pip" aria-hidden="true"></div>
          <input
            id="mindbridge-input-field"
            type="text"
            placeholder="Chat with Ellen..."
            autocomplete="off"
            required
          />
          <button id="mindbridge-send-btn" type="submit" aria-label="Send Message">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
            </svg>
          </button>
        </div>
      </form>
    </div>
  `;
  document.body.appendChild(container);

  // Element references
  const launcherBtn = document.getElementById('mindbridge-launcher-btn');
  const chatWindow = document.getElementById('mindbridge-chat-window');
  const closeBtn = document.getElementById('mindbridge-close-btn');
  const resetBtn = document.getElementById('mindbridge-reset-btn');
  const welcomeView = document.getElementById('mindbridge-welcome-view');
  const messageList = document.getElementById('mindbridge-message-list');
  const chatForm = document.getElementById('mindbridge-chat-footer');
  const inputField = document.getElementById('mindbridge-input-field');
  const sendBtn = document.getElementById('mindbridge-send-btn');
  const starterCards = document.querySelectorAll('.mindbridge-starter-card');

  let isOpen = false;
  let isSending = false;

  // Session Management via sessionStorage
  function getSessionId() {
    return sessionStorage.getItem(STORAGE_KEY_SESSION) || null;
  }

  function setSessionId(id) {
    if (id) {
      sessionStorage.setItem(STORAGE_KEY_SESSION, id);
    }
  }

  function getHistory() {
    try {
      return JSON.parse(sessionStorage.getItem(STORAGE_KEY_HISTORY) || '[]');
    } catch {
      return [];
    }
  }

  function saveHistory(history) {
    sessionStorage.setItem(STORAGE_KEY_HISTORY, JSON.stringify(history));
  }

  function clearHistory() {
    sessionStorage.removeItem(STORAGE_KEY_HISTORY);
    sessionStorage.removeItem(STORAGE_KEY_SESSION);
  }

  // Safe HTML parser & sanitizer for Assistant messages with Markdown support
  function parseAssistantTextToFragment(rawText) {
    let text = rawText || '';

    // Normalize encoded characters or weird apostrophes
    text = text.replace(/\?\?m/g, "’m")
               .replace(/\?\?re/g, "’re")
               .replace(/\?\?s/g, "’s")
               .replace(/\?\?t/g, "’t")
               .replace(/\?\?/g, "—");

    // Replace Markdown bold **text** with <strong>text</strong>
    text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    // If text contains HTML tags like <br> or <p>
    if (!/<br\s*\/?>/i.test(text) && !/<p>/i.test(text)) {
      // Split on double line breaks into paragraphs
      const paragraphs = text.split(/\n{2,}/);
      if (paragraphs.length > 1) {
        text = paragraphs.map(p => `<p>${p.replace(/\n/g, '<br>')}</p>`).join('');
      } else {
        text = text.replace(/\n/g, '<br>');
      }
    }

    const parser = new DOMParser();
    const doc = parser.parseFromString(text, 'text/html');
    const allowedTags = new Set(['B', 'BR', 'UL', 'OL', 'LI', 'I', 'EM', 'STRONG', 'P', 'SPAN']);

    function cleanNode(node) {
      const fragment = document.createDocumentFragment();
      for (const child of Array.from(node.childNodes)) {
        if (child.nodeType === Node.TEXT_NODE) {
          fragment.appendChild(document.createTextNode(child.textContent));
        } else if (child.nodeType === Node.ELEMENT_NODE) {
          const tagName = child.tagName.toUpperCase();
          if (allowedTags.has(tagName)) {
            const cleanElem = document.createElement(tagName.toLowerCase());
            cleanElem.appendChild(cleanNode(child));
            fragment.appendChild(cleanElem);
          } else {
            fragment.appendChild(cleanNode(child));
          }
        }
      }
      return fragment;
    }

    return cleanNode(doc.body);
  }

  // Welcoming Dynamic Word Ticker
  const TICKER_WORDS = ['heal.', 'grow.', 'breathe.', 'thrive.', 'find peace.', 'feel heard.', 'find clarity.'];
  let tickerIndex = 0;
  let tickerTimer = null;

  function startTicker() {
    stopTicker();
    const tickerEl = document.getElementById('mindbridge-ticker-text');
    if (!tickerEl) return;

    tickerTimer = setInterval(() => {
      tickerEl.classList.add('ticker-slide-out');
      setTimeout(() => {
        tickerIndex = (tickerIndex + 1) % TICKER_WORDS.length;
        tickerEl.textContent = TICKER_WORDS[tickerIndex];
        tickerEl.classList.remove('ticker-slide-out');
        tickerEl.classList.add('ticker-slide-in');
        void tickerEl.offsetWidth; // Force reflow
        tickerEl.classList.remove('ticker-slide-in');
      }, 360);
    }, 2400);
  }

  function stopTicker() {
    if (tickerTimer) {
      clearInterval(tickerTimer);
      tickerTimer = null;
    }
  }

  // Switch between Welcome View and Active Message List
  function showActiveChatView() {
    stopTicker();
    welcomeView.style.display = 'none';
    messageList.style.display = 'flex';
  }

  function showWelcomeView() {
    messageList.style.display = 'none';
    messageList.innerHTML = '';
    welcomeView.style.display = 'flex';
    startTicker();
  }

  // Render a message into the chat window
  function appendMessage(role, text) {
    showActiveChatView();
    const msgDiv = document.createElement('div');
    msgDiv.className = `mindbridge-message ${role}`;
    if (role === 'assistant') {
      msgDiv.appendChild(parseAssistantTextToFragment(text));
    } else {
      msgDiv.textContent = text;
    }
    messageList.appendChild(msgDiv);
    messageList.scrollTop = messageList.scrollHeight;
  }

  // Show pulsing gradient loading indicator
  function showTypingIndicator() {
    showActiveChatView();
    const indicator = document.createElement('div');
    indicator.id = 'mindbridge-typing-indicator';
    indicator.className = 'mindbridge-typing-indicator';
    indicator.innerHTML = `
      <div class="mindbridge-typing-dot"></div>
      <div class="mindbridge-typing-dot"></div>
      <div class="mindbridge-typing-dot"></div>
    `;
    messageList.appendChild(indicator);
    messageList.scrollTop = messageList.scrollHeight;
  }

  function hideTypingIndicator() {
    const indicator = document.getElementById('mindbridge-typing-indicator');
    if (indicator) {
      indicator.remove();
    }
  }

  // Open Chat Window
  function openChat() {
    isOpen = true;
    chatWindow.style.display = 'flex';
    launcherBtn.style.display = 'none';

    const history = getHistory();
    if (history.length > 0) {
      showActiveChatView();
      messageList.innerHTML = '';
      history.forEach((m) => appendMessage(m.role, m.text));
    } else {
      // First time open: show the soothing animated aura, ticker & 3 starter cards!
      showWelcomeView();
    }

    inputField.focus();
  }

  // Close Chat Window
  function closeChat() {
    isOpen = false;
    stopTicker();
    chatWindow.style.display = 'none';
    launcherBtn.style.display = 'flex';
  }

  // Reset conversation to fresh state
  function resetChat() {
    clearHistory();
    showWelcomeView();
    inputField.value = '';
    inputField.focus();
  }

  launcherBtn.addEventListener('click', openChat);
  closeBtn.addEventListener('click', closeChat);
  resetBtn.addEventListener('click', resetChat);

  // Core send message logic
  async function sendMessage(text) {
    const cleanText = (text || '').trim();
    if (!cleanText || isSending) return;

    // Switch to active chat and append user message
    showActiveChatView();
    appendMessage('user', cleanText);

    const history = getHistory();
    history.push({ role: 'user', text: cleanText });
    saveHistory(history);

    inputField.value = '';
    isSending = true;
    sendBtn.disabled = true;
    showTypingIndicator();

    const sessionId = getSessionId();

    try {
      const response = await fetch(`${MINDBRIDGE_BACKEND_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          message: cleanText,
        }),
      });

      hideTypingIndicator();

      if (!response.ok) {
        throw new Error(`HTTP error ${response.status}`);
      }

      const data = await response.json();
      if (data.session_id) {
        setSessionId(data.session_id);
      }

      const reply = data.response || 'Thank you for reaching out to MindBridge Wellness.';
      appendMessage('assistant', reply);

      history.push({ role: 'assistant', text: reply });
      saveHistory(history);
    } catch (err) {
      hideTypingIndicator();
      console.error('[MindBridge Widget Error]:', err);
      appendMessage(
        'error',
        'Unable to connect to our care assistant right now. Please try again, or reach out directly at care@mindbridgewellness.demo or (555) 349-2810.'
      );
    } finally {
      isSending = false;
      sendBtn.disabled = false;
      inputField.focus();
    }
  }

  // Starter cards click handlers
  starterCards.forEach((card) => {
    card.addEventListener('click', () => {
      const prompt = card.getAttribute('data-prompt');
      if (prompt) {
        sendMessage(prompt);
      }
    });
  });

  // Form submit handler
  chatForm.addEventListener('submit', (e) => {
    e.preventDefault();
    sendMessage(inputField.value);
  });

  // Expose public API on window for external buttons & landing page triggers
  window.MindBridge = {
    open: openChat,
    close: closeChat,
    send: sendMessage,
    reset: resetChat
  };
})();
