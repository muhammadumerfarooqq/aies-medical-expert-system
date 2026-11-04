"""Brand constants and CSS for the Shifa wizard UI. Offline: system fonts only, no external assets.

All motion is CSS (keyframes + animation-delay). There is no JavaScript and no timer.
"""

APP_NAME = "Shifa"
TAGLINE = "Rule-based diagnosis. Every answer explained."
OFFICIAL_TITLE = "Intelligent Medical Diagnosis Expert System"
FOOTER = ("Educational tool, not medical advice. In an emergency call your local "
          "emergency number.")
VIEWS = ["Consult", "Knowledge base"]
STEPS = ["Symptoms", "Severity", "Reasoning", "Diagnosis"]
MAX_CHAIN_SECONDS = 4.0     # a chain panel never takes longer than this to build
MAX_GAP_SECONDS = 0.8       # delay between two chain steps

# The three diseases used as "one example per severity level" in the knowledge-base view.
# Their severities (severe, moderate, mild) are asserted in ui/components.py.
KB_SHOWCASE = ("dengue", "influenza", "common_cold")
# Course requirement for the knowledge-base view: minimum symptoms / diseases.
REQUIREMENTS = {"symptoms": 8, "diseases": 3}

# Logo: a heartbeat line in a rounded teal square. Fully visible by default; the gentle
# pulse (opacity/scale) is a CSS loop that is switched off for prefers-reduced-motion.
MARK_SVG = (
    '<svg class="mark" viewBox="0 0 48 48" role="img" aria-label="Shifa heartbeat logo">'
    '<rect width="48" height="48" rx="12" fill="#0F766E"/>'
    '<path class="beat" d="M6 26 H16 L20 14 L26 36 L30 22 L33 26 H42" fill="none" '
    'stroke="#FFFFFF" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>'
    '</svg>')

CSS = """
<style>
:root{--accent:#0F766E;--accent-dark:#0B5F58;--accent-soft:#E3F3F1;--ink:#17212B;--muted:#46535F;
--line:#D5DCE2;--card:#FFFFFF;--bg:#F5F8F8;--sev3:#B42318;--sev3-bg:#FEE4E2;--sev2:#8A4B05;
--sev2-bg:#FEF0C7;--sev1:#166534;--sev1-bg:#DCFCE7;
--fw:#1D4ED8;--fw-t:#DBEAFE;--bw:#6D28D9;--bw-t:#EDE9FE;}
html,body,[data-testid="stAppViewContainer"],.stApp{background:var(--bg);color:var(--ink);
font-family:"Segoe UI",system-ui,-apple-system,Roboto,Arial,sans-serif;font-size:18px;line-height:1.5;}
.stApp p,.stApp li,.stApp label{font-size:18px;}
[data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] p{font-size:15px !important;color:var(--muted);}
#MainMenu,footer,[data-testid="stToolbar"],[data-testid="stDecoration"],
[data-testid="stStatusWidget"],.stDeployButton,header[data-testid="stHeader"]{display:none !important;}
[data-testid="stMainBlockContainer"],.block-container{max-width:none !important;
padding:.75rem 3rem 1rem 3rem !important;}
[data-testid="stVerticalBlock"]{gap:.55rem;}
/* Streamlit pulls HTML-only markdown up by 1rem (to cancel paragraph margins): undo that. */
[data-testid="stMarkdownContainer"]{margin-bottom:0 !important;}
[data-testid="stMarkdownContainer"] p{margin:0 0 .35rem 0;}
[data-testid="stButtonGroup"]>div:last-child{flex-wrap:wrap !important;overflow:visible !important;gap:.5rem;}
.st-key-topbar{margin-bottom:.9rem;min-height:0;}
[data-testid="stBottom"],[data-testid="stBottom"]>div{background:var(--bg) !important;}
h1,h2,h3{color:var(--ink);} .h-big{font-size:32px;font-weight:700;margin:0 0 .3rem 0;line-height:1.2;}
/* ---- buttons, chips, selectors (icons keep their own font) */
.stButton>button,[data-testid^="stBaseButton"]{min-height:44px;font-size:17px;border-radius:14px;font-weight:600;}
.stButton>button{border:1.5px solid var(--accent);color:var(--accent-dark);background:#fff;}
.stButton>button[kind="primary"]{background:var(--accent);color:#fff;border-color:var(--accent);}
button[data-testid="stBaseButton-pills"],button[data-testid="stBaseButton-pillsActive"]{min-height:44px;
font-size:17px;padding:0 18px;border-radius:999px;}
[data-testid^="stBaseButton-segmented_control"]{min-height:44px;font-size:16px;white-space:nowrap;}
.stButton>button:focus-visible,[data-testid^="stBaseButton"]:focus-visible{outline:3px solid #7DD3C8;outline-offset:2px;}
[data-testid="stChatInput"]{border:2px solid var(--muted);border-radius:16px;background:#fff;}
[data-testid="stChatInput"]:focus-within{border-color:var(--accent);box-shadow:0 0 0 3px #7DD3C8;}
[data-testid="stChatInput"] textarea{font-size:18px !important;color:var(--ink);}
[data-testid="stChatInput"] textarea::placeholder{color:var(--muted);opacity:1;}
[data-testid="stBottom"]{background:transparent;}
div[class*="st-key-card-"]{background:var(--card);border:1px solid var(--line);border-radius:16px;
padding:.8rem 1rem;box-shadow:0 2px 10px rgba(16,24,40,.07);}
/* ---- top bar */
.brand{display:flex;align-items:center;gap:.7rem;}
.brand .mark{width:46px;height:46px;flex:none;}
.brand .name{font-size:26px;font-weight:700;line-height:1.1;}
.brand .tag{color:var(--muted);font-size:15px;line-height:1.2;}
.brand .official{display:none;}
.beat{transform-origin:24px 24px;animation:pulse 2.4s ease-in-out infinite;}
.stepsbar{display:flex;gap:.35rem;justify-content:center;flex-wrap:nowrap;}
.stepsbar .s{border:1.5px solid var(--line);background:#fff;border-radius:999px;padding:.2rem .8rem;
font-size:16px;color:var(--muted);white-space:nowrap;}
.stepsbar .s.done{background:var(--accent-soft);color:var(--accent-dark);border-color:var(--accent);}
.stepsbar .s.now{background:var(--accent);color:#fff;border-color:var(--accent);font-weight:700;}
/* ---- chips and small text */
.chips{display:flex;flex-wrap:wrap;gap:.4rem;margin:.3rem 0;}
.chip{display:inline-block;background:var(--accent-soft);color:#0B4F4A;border-radius:999px;
padding:.15rem .8rem;font-size:16px;}
.chip.derived{background:#fff;border:1.5px dashed var(--accent);color:var(--accent-dark);}
.chip.out{background:#EEF1F4;color:var(--muted);}
.chip.danger{background:var(--sev3-bg);color:var(--sev3);font-weight:700;}
.chip.ok{background:var(--sev1-bg);color:var(--sev1);font-weight:600;}
.chip.no{background:#EEF1F4;color:var(--muted);font-weight:600;}
.tagc{display:inline-block;font-size:15px;font-weight:800;letter-spacing:.03em;border-radius:8px;
padding:0 .55rem;margin-right:.4rem;color:#fff;background:var(--pc,var(--accent));}
.tagc.fail{background:#6B7280;}
.tag{font-size:15px;color:var(--accent-dark);margin-left:.2rem;}
.small{color:var(--muted);font-size:15px;}
.rbadge{display:inline-block;background:var(--pc,var(--accent));color:#fff;border-radius:8px;
padding:0 .55rem;font-weight:700;margin:0 .3rem;font-size:16px;}
.arrow{color:var(--muted);font-weight:700;margin:0 .15rem;}
/* ---- cards, verdict, tiers */
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:.8rem 1rem;
box-shadow:0 2px 10px rgba(16,24,40,.07);}
.card .top{display:flex;align-items:center;justify-content:space-between;gap:.5rem;flex-wrap:wrap;}
.card .name{font-size:22px;font-weight:700;}
.card .rank{color:var(--muted);margin-right:.4rem;}
.pill{display:inline-block;border-radius:999px;padding:.1rem .8rem;font-size:16px;font-weight:700;}
.sev3{background:var(--sev3-bg);color:var(--sev3);}
.sev2{background:var(--sev2-bg);color:var(--sev2);}
.sev1{background:var(--sev1-bg);color:var(--sev1);}
.tied{display:inline-block;border:1.5px solid var(--muted);color:var(--muted);border-radius:999px;
padding:0 .6rem;font-size:15px;margin-left:.4rem;}
.big{font-size:48px;font-weight:700;line-height:1.05;color:var(--accent-dark);}
.bar{height:12px;background:#E3E8EA;border-radius:999px;overflow:hidden;margin:.3rem 0;}
.bar>span{display:block;height:100%;border-radius:999px;background:var(--accent);}
.bar.sev3>span{background:var(--sev3);} .bar.sev2>span{background:#D97706;} .bar.sev1>span{background:#16A34A;}
.bar.sev3,.bar.sev2,.bar.sev1{background:#E3E8EA;}
.fade{animation:fadein .5s ease-out both;} .fade .bar>span{animation:grow 1s ease-out both;}
.verdict{background:var(--accent);color:#fff;border-radius:16px;padding:.7rem 1.2rem;
box-shadow:0 3px 12px rgba(15,118,110,.3);}
.verdict .head{font-size:28px;font-weight:700;line-height:1.2;}
.verdict .sub{font-size:17px;opacity:.97;}
.verdict.none{background:#fff;color:var(--ink);border:2px solid var(--muted);box-shadow:none;}
.tier{font-size:20px;font-weight:700;margin:.2rem 0 .3rem 0;padding-bottom:.2rem;border-bottom:2px solid var(--line);}
.panel{background:#F8FAFB;border:1px solid var(--line);border-radius:12px;padding:.6rem .8rem;margin:.3rem 0;}
.panel ul{margin:.2rem 0;padding-left:1.2rem;} .panel li{font-size:16px;}
.alert{background:var(--sev3-bg);border:2px solid var(--sev3);color:#6B1710;border-radius:16px;
padding:.6rem 1.1rem;font-size:18px;}
.alert b{color:var(--sev3);}
/* ---- chain panels (forward = blue, backward = violet) */
.pf{--pc:var(--fw);--pt:var(--fw-t);} .pb{--pc:var(--bw);--pt:var(--bw-t);}
.pheader{display:inline-block;background:var(--pc);color:#fff;border-radius:10px;padding:.15rem .8rem;
font-weight:800;font-size:17px;margin:.1rem 0 .3rem 0;}
.pheader span{font-weight:500;opacity:.95;margin-left:.4rem;}
.chain{border:2px solid var(--pc);border-radius:14px;background:#fff;padding:.5rem .6rem .6rem .6rem;margin-bottom:.6rem;}
.pbar{height:6px;background:var(--pt);border-radius:999px;overflow:hidden;margin-bottom:.5rem;}
.pbar>span{display:block;height:100%;background:var(--pc);width:100%;transform-origin:left;
animation:fillbar var(--total) linear both;}
.chain .step{position:relative;background:var(--pt);border-left:4px solid var(--pc);border-radius:10px;
padding:.25rem .6rem;margin:0 0 10px 0;font-size:17px;opacity:0;transform:translateY(8px);
animation:stepin .45s ease-out both,hot var(--gap) ease-out both;
animation-delay:calc(var(--i) * var(--gap)),calc(var(--i) * var(--gap));}
.chain .step:last-child{margin-bottom:0;}
.chain .step:not(:last-child)::after{content:"";position:absolute;left:18px;bottom:-10px;height:10px;
border-left:3px solid var(--pc);}
.chain.static .step,.chain.static .pbar>span{animation:none;opacity:1;transform:none;}
.chain.static .glow{animation:none;}
.glow{animation:glow 1.3s ease-out both;animation-delay:calc(var(--i) * var(--gap) + .3s);}
.cap{display:inline;color:var(--muted);font-size:15px;margin-left:.5rem;}
.step.proof{background:var(--sev1-bg);border-left-color:var(--sev1);}
.step.proof.fail{background:#EEF1F4;border-left-color:#6B7280;}
.step.ask{animation:stepin .45s ease-out both,hot var(--gap) ease-out both,pulse2 1.2s ease-in-out 2;
animation-delay:calc(var(--i) * var(--gap)),calc(var(--i) * var(--gap)),calc(var(--i) * var(--gap) + .4s);}
.chain.static .step.ask{animation:none;}
div[class*="st-key-col-"]{max-height:calc(100vh - 250px);overflow-y:auto;padding-right:.3rem;}
.muted-card{background:#fff;border:1.5px dashed var(--muted);border-radius:14px;padding:.8rem 1rem;color:var(--muted);}
/* ---- knowledge base view */
.tile{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:.6rem .9rem;}
.tile b{font-size:18px;} .tile .v{font-size:17px;}
.ok-tick{color:var(--sev1);font-weight:700;}
div[class*="st-key-kbtile-"] button{height:auto;min-height:92px;align-items:flex-start;justify-content:flex-start;text-align:left;white-space:normal;padding:.5rem .9rem;background:#fff;}
div[class*="st-key-kbtile-"] button p{text-align:left;margin:0;font-size:17px;line-height:1.35;}
div[class*="st-key-kbtile-"] button *{white-space:normal !important;overflow:visible !important;text-overflow:clip !important;text-align:left !important;}
div[class*="st-key-kbtile-"] button div{justify-content:flex-start !important;}
.kbcard .chip{font-size:15px;padding:.05rem .55rem;}
.kbcard li,.kbcard .alert{font-size:15px !important;line-height:1.35;}
.kbcard{padding:.6rem .9rem;}
.strip{background:var(--accent-soft);border-radius:12px;padding:.4rem .9rem;font-size:16px;}
.footer{color:var(--muted);font-size:15px;text-align:center;margin:.3rem 0 0 0;}
@keyframes fadein{from{opacity:0;transform:translateY(10px);}to{opacity:1;transform:none;}}
@keyframes grow{from{width:0;}}
@keyframes fillbar{from{transform:scaleX(0);}to{transform:scaleX(1);}}
@keyframes stepin{from{opacity:0;transform:translateY(8px);}to{opacity:1;transform:none;}}
@keyframes hot{0%{border-left-width:10px;box-shadow:0 0 0 4px var(--pt);}100%{border-left-width:4px;box-shadow:none;}}
@keyframes glow{0%{box-shadow:0 0 0 0 rgba(15,118,110,.7);}60%{box-shadow:0 0 0 10px rgba(15,118,110,0);}
100%{box-shadow:none;}}
@keyframes pulse2{0%,100%{outline:0 solid rgba(109,40,217,.5);}50%{outline:6px solid rgba(109,40,217,.25);}}
@keyframes pulse{0%,100%{opacity:.8;transform:scale(.97);}50%{opacity:1;transform:scale(1.03);}}
@media (max-width:1500px){.stepsbar .s{padding:.15rem .55rem;font-size:15px;}.brand .tag{font-size:15px;}
.brand .name{font-size:24px;}}
@media (max-width:760px){[data-testid="stMainBlockContainer"]{padding:.5rem 1rem !important;}
.big{font-size:40px;} .stepsbar .s{font-size:15px;padding:.2rem .5rem;}}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation:none !important;
transition:none !important;}.chain .step{opacity:1 !important;transform:none !important;}}
</style>
"""
