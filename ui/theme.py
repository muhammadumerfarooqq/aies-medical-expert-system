"""Brand constants and CSS for the Shifa wizard UI. Offline: system fonts only, no external assets.

All motion is CSS (keyframes + animation-delay). There is no JavaScript and no timer.
Every size is in rem, and the root font size is ONE scale variable (--u) that grows with the
window, so text, padding, chips, buttons, cards and icons all grow together.
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
:root{--u:clamp(15px,calc(0.5vw + 0.8vh + 4.6px),25px);
--accent:#0F766E;--accent-dark:#0B5F58;--accent-soft:#E3F3F1;--ink:#17212B;--muted:#46535F;
--line:#D5DCE2;--card:#FFFFFF;--bg:#F5F8F8;--sev3:#B42318;--sev3-bg:#FEE4E2;--sev2:#8A4B05;
--sev2-bg:#FEF0C7;--sev1:#166534;--sev1-bg:#DCFCE7;
--fw:#1D4ED8;--fw-t:#DBEAFE;--bw:#6D28D9;--bw-t:#EDE9FE;
--small:max(15px,.86rem);--radius:.9rem;--chrome:7.7rem;}
html{font-size:var(--u) !important;}
html,body,[data-testid="stAppViewContainer"],.stApp{background:var(--bg);color:var(--ink);
font-family:"Segoe UI",system-ui,-apple-system,Roboto,Arial,sans-serif;font-size:1rem;line-height:1.5;}
.stApp p,.stApp li,.stApp label{font-size:1rem;}
[data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] p{font-size:var(--small) !important;color:var(--muted);}
#MainMenu,footer,[data-testid="stToolbar"],[data-testid="stDecoration"],
[data-testid="stStatusWidget"],.stDeployButton,header[data-testid="stHeader"]{display:none !important;}
[data-testid="stMainBlockContainer"],.block-container{max-width:none !important;
padding:.6rem 2.2rem .5rem 2.2rem !important;}
[data-testid="stVerticalBlock"]{gap:.5rem;}
/* Streamlit pulls HTML-only markdown up by 1rem (to cancel paragraph margins): undo that. */
[data-testid="stMarkdownContainer"]{margin-bottom:0 !important;}
[data-testid="stMarkdownContainer"] p{margin:0 0 .35rem 0;}
[data-testid="stButtonGroup"]>div:last-child{flex-wrap:wrap !important;overflow:visible !important;gap:.6rem;}
.st-key-topbar{margin-bottom:.6rem;min-height:0;}
[data-testid="stBottom"],[data-testid="stBottom"]>div{background:var(--bg) !important;}
h1,h2,h3{color:var(--ink);}
.h-big{font-size:1.85rem;font-weight:800;margin:0 0 .3rem 0;line-height:1.2;}
/* ---- one stage per step: fills the window, action bar at the bottom
   (Streamlit wraps every container in a stLayoutWrapper, so the wrappers are targeted) */
.st-key-stage{min-height:calc(100vh - var(--chrome));display:flex;flex-direction:column;}
[data-testid="stBottomBlockContainer"]{padding:.2rem 2.2rem .5rem 2.2rem !important;}
.st-key-stage:has(.st-key-card-type){min-height:calc(100vh - 11.8rem);}
.st-key-stage>[data-testid="stLayoutWrapper"]:has(>.st-key-grow){flex:1 1 auto;}
.st-key-stage>[data-testid="stLayoutWrapper"]:has(>.st-key-bar){margin-top:auto;}
.st-key-grow{flex:1 1 auto;display:flex;flex-direction:column;}
.st-key-grow>[data-testid="stLayoutWrapper"]{flex:1 1 auto;}
.st-key-grow>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]{flex:1 1 auto;align-items:stretch;}
.st-key-grow [data-testid="stColumn"]{display:flex;flex-direction:column;}
.st-key-grow [data-testid="stColumn"]>[data-testid="stVerticalBlock"]{flex:1 1 auto;}
.st-key-grow [data-testid="stVerticalBlock"]>[data-testid="stLayoutWrapper"]:has(>[data-testid="stHorizontalBlock"]),
.st-key-grow [data-testid="stVerticalBlock"]>[data-testid="stLayoutWrapper"]:has(>[class*="st-key-card-"]){flex:1 1 auto;}
.st-key-grow [data-testid="stLayoutWrapper"]>[class*="st-key-card-"]{height:100%;}
/* ---- crowded cases: only a dedicated area scrolls; top bar, banners and action bar stay put */
.st-key-stage:has(.st-key-grow-scroll){height:calc(100vh - var(--chrome));min-height:0;flex:none;}
.st-key-stage>[data-testid="stLayoutWrapper"]:has(>.st-key-grow-scroll){flex:1 1 0;min-height:0;}
.st-key-grow-scroll{overflow-y:auto;min-height:0;flex:1 1 0;padding-right:.4rem;}
.tier{white-space:nowrap;}
.card.compact{padding:.7rem 1rem;}
.card.compact .name{font-size:1.2rem;}
.card.compact .big{font-size:1.95rem;}
.card.compact .rank{font-size:1rem;}
.alert.multi{padding:.5rem 1.2rem;}
.alert.multi ul{margin:.2rem 0 0 0;padding-left:1.2rem;}
.alert.multi li{font-size:max(15px,.85rem);line-height:1.35;}
.alert.multi .rfhead{font-size:1.05rem;letter-spacing:.12em;}
.sevhead{display:flex;gap:1rem;align-items:baseline;flex-wrap:wrap;}
.sidecount{font-weight:700;font-size:1rem;}
div[class*="st-key-card-csev-"]{flex-direction:row !important;align-items:center;justify-content:space-between;
gap:.5rem;padding:.45rem .7rem;height:auto;}
div[class*="st-key-card-csev-"]>[data-testid]{min-width:0;flex:0 0 auto;}
div[class*="st-key-card-csev-"]>[data-testid]:first-child{flex:1 1 0;}
div[class*="st-key-card-csev-"]>[data-testid]:last-child{width:auto !important;flex:0 0 auto;}
div[class*="st-key-card-csev-"]>[data-testid]:first-child{width:auto !important;}
div[class*="st-key-card-csev-"] b{font-size:max(15px,.72rem);line-height:1.2;overflow-wrap:normal;word-break:normal;}
div[class*="st-key-card-csev-"] [role="radiogroup"]{flex-wrap:nowrap !important;gap:0;}
div[class*="st-key-card-csev-"] [role="radiogroup"] button{font-size:max(15px,.7rem);min-height:2rem;padding:0 .35rem;}
div[class*="st-key-card-csev-"] [role="radiogroup"] button p{font-size:inherit;margin:0;white-space:nowrap;}
/* Why this? | Treatment | Prevention: one row of three equal buttons, never wrapped */
div[class*="-tab-"]{container-type:inline-size;width:100%;}
div[class*="-tab-"] [data-testid="stButtonGroup"]{width:100%;}
div[class*="-tab-"] [role="radiogroup"]{display:flex;flex-wrap:nowrap !important;width:100%;gap:.3rem;}
div[class*="-tab-"] [role="radiogroup"] button{flex:1 1 0 !important;min-width:0;white-space:nowrap;overflow:hidden;
text-overflow:ellipsis;padding:0 .3rem;justify-content:center;font-size:clamp(15px,4.4cqw,.9rem);}
div[class*="-tab-"] [role="radiogroup"] button p{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
font-size:inherit;margin:0;}
/* ---- buttons, chips, selectors (icons keep their own font) */
.stButton>button,[data-testid^="stBaseButton"]{min-height:2.3rem;font-size:.9rem;border-radius:var(--radius);font-weight:600;}
.stButton>button p,[data-testid^="stBaseButton"] p{font-size:.9rem;}
.stButton>button{border:1.5px solid var(--accent);color:var(--accent-dark);background:#fff;}
.stButton>button[kind="primary"]{background:var(--accent);color:#fff;border-color:var(--accent);}
button[data-testid="stBaseButton-pills"],button[data-testid="stBaseButton-pillsActive"]{min-height:2.3rem;
font-size:.9rem;padding:0 1.1rem;border-radius:999px;}
[data-testid^="stBaseButton-segmented_control"]{min-height:2.3rem;font-size:max(15px,.85rem);white-space:nowrap;padding:0 1rem;}
.stButton>button:focus-visible,[data-testid^="stBaseButton"]:focus-visible{outline:3px solid #7DD3C8;outline-offset:2px;}
[data-testid="stChatInput"]{border:2px solid var(--muted);border-radius:var(--radius);background:#fff;}
[data-testid="stChatInput"]:focus-within{border-color:var(--accent);box-shadow:0 0 0 3px #7DD3C8;}
[data-testid="stChatInput"] textarea{font-size:1rem !important;color:var(--ink);}
[data-testid="stChatInput"] textarea::placeholder{color:var(--muted);opacity:1;}
div[class*="st-key-card-"]{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
padding:1rem 1.2rem;box-shadow:0 2px 10px rgba(16,24,40,.07);}
div[class*="st-key-card-"]{height:100%;}
/* ---- top bar */
.brand{display:flex;align-items:center;gap:.8rem;}
.brand .mark{width:2.5rem;height:2.5rem;flex:none;}
.brand .name{font-size:1.25rem;font-weight:800;line-height:1.1;}
.brand .tag{color:var(--muted);font-size:max(15px,.7rem);line-height:1.2;white-space:nowrap;}
.brand .name{white-space:nowrap;}
.beat{transform-origin:24px 24px;animation:pulse 2.4s ease-in-out infinite;}
.stepsbar{display:flex;gap:.4rem;justify-content:center;flex-wrap:nowrap;}
.stepsbar .s{border:1.5px solid var(--line);background:#fff;border-radius:999px;padding:.2rem .9rem;
font-size:max(15px,.8rem);color:var(--muted);white-space:nowrap;}
.stepsbar .s.done{background:var(--accent-soft);color:var(--accent-dark);border-color:var(--accent);}
.stepsbar .s.now{background:var(--accent);color:#fff;border-color:var(--accent);font-weight:700;}
/* ---- chips and small text */
.chips{display:flex;flex-wrap:wrap;gap:.45rem;margin:.3rem 0;}
.chip{display:inline-block;background:var(--accent-soft);color:#0B4F4A;border-radius:999px;
padding:.15rem .9rem;font-size:max(15px,.85rem);}
.chip.derived{background:#fff;border:1.5px dashed var(--accent);color:var(--accent-dark);}
.chip.out{background:#EEF1F4;color:var(--muted);}
.chip.danger{background:var(--sev3-bg);color:var(--sev3);font-weight:700;}
.chip.ok{background:var(--sev1-bg);color:var(--sev1);font-weight:600;}
.chip.no{background:#EEF1F4;color:var(--muted);font-weight:600;}
.tagc{display:inline-block;font-size:max(15px,.75rem);font-weight:800;letter-spacing:.03em;border-radius:8px;
padding:0 .6rem;margin-right:.45rem;color:#fff;background:var(--pc,var(--accent));}
.tagc.fail{background:#6B7280;}
.tag{font-size:max(15px,.8rem);color:var(--accent-dark);margin-left:.2rem;}
.small{color:var(--muted);font-size:var(--small);}
.rbadge{display:inline-block;background:var(--pc,var(--accent));color:#fff;border-radius:8px;
padding:0 .6rem;font-weight:700;margin:0 .3rem;font-size:max(15px,.85rem);}
.arrow{color:var(--muted);font-weight:700;margin:0 .15rem;}
/* ---- cards, verdict, tiers */
.card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:.9rem 1.3rem;
box-shadow:0 2px 10px rgba(16,24,40,.07);}
.card .top{display:flex;align-items:center;justify-content:space-between;gap:.5rem;flex-wrap:wrap;}
.card .name{font-size:1.4rem;font-weight:800;}
.card .rank{color:var(--muted);margin-right:.4rem;font-size:1.1rem;}
.pill{display:inline-block;border-radius:999px;padding:.1rem .9rem;font-size:max(15px,.85rem);font-weight:700;}
.sev3{background:var(--sev3-bg);color:var(--sev3);}
.sev2{background:var(--sev2-bg);color:var(--sev2);}
.sev1{background:var(--sev1-bg);color:var(--sev1);}
.tied{display:inline-block;border:1.5px solid var(--muted);color:var(--muted);border-radius:999px;
padding:0 .7rem;font-size:max(15px,.8rem);margin-left:.5rem;}
.big{font-size:2.8rem;font-weight:800;line-height:1.05;color:var(--accent-dark);}
.big .small{font-weight:600;}
.bar{height:.7rem;background:#E3E8EA;border-radius:999px;overflow:hidden;margin:.4rem 0;}
.bar>span{display:block;height:100%;border-radius:999px;background:var(--accent);}
.bar.sev3>span{background:var(--sev3);} .bar.sev2>span{background:#D97706;} .bar.sev1>span{background:#16A34A;}
.bar.sev3,.bar.sev2,.bar.sev1{background:#E3E8EA;}
.fade{animation:fadein .5s ease-out both;} .fade .bar>span{animation:grow 1s ease-out both;}
.verdict{background:var(--accent);color:#fff;border-radius:var(--radius);padding:.7rem 1.5rem .8rem 1.5rem;
box-shadow:0 3px 12px rgba(15,118,110,.3);}
.verdict .lbl{font-size:max(15px,.8rem);font-weight:800;letter-spacing:.18em;opacity:.9;}
.verdict .row{display:flex;align-items:baseline;gap:1.4rem;flex-wrap:wrap;}
.verdict .vname{font-size:2.8rem;font-weight:800;line-height:1.1;}
.verdict .vconf{font-size:2.45rem;font-weight:800;line-height:1.1;}
.verdict .vsev{font-size:1.05rem;font-weight:800;border-radius:999px;padding:.1rem 1rem;background:#fff;color:var(--ink);align-self:center;}
.verdict .sub{font-size:.95rem;opacity:.98;margin-top:.3rem;}
.verdict.none{background:#fff;color:var(--ink);border:2px solid var(--muted);box-shadow:none;}
.verdict.none .vname{font-size:2.4rem;}
.tier{font-size:1.2rem;font-weight:800;margin:.2rem 0 .4rem 0;padding-bottom:.25rem;border-bottom:2px solid var(--line);}
.panel{background:#F8FAFB;border:1px solid var(--line);border-radius:12px;padding:.7rem .9rem;margin:.3rem 0;}
.panel ul{margin:.2rem 0;padding-left:1.2rem;} .panel li{font-size:max(15px,.85rem);}
.alert{background:var(--sev3-bg);border:2px solid var(--sev3);color:#6B1710;border-radius:var(--radius);
padding:.7rem 1.3rem;font-size:1.05rem;font-weight:700;}
.alert b{color:var(--sev3);font-weight:800;}
/* ---- chain panels (forward = blue, backward = violet) */
.pf{--pc:var(--fw);--pt:var(--fw-t);} .pb{--pc:var(--bw);--pt:var(--bw-t);}
.pheader{display:inline-block;background:var(--pc);color:#fff;border-radius:10px;padding:.2rem .9rem;
font-weight:800;font-size:.9rem;margin:.1rem 0 .4rem 0;}
.pheader span{font-weight:500;opacity:.95;margin-left:.5rem;}
.chain{border:2px solid var(--pc);border-radius:var(--radius);background:#fff;padding:.6rem .7rem .7rem .7rem;margin-bottom:.6rem;}
.pbar{height:.35rem;background:var(--pt);border-radius:999px;overflow:hidden;margin-bottom:.6rem;}
.pbar>span{display:block;height:100%;background:var(--pc);width:100%;transform-origin:left;
animation:fillbar var(--total) linear both;}
.chain .step{position:relative;background:var(--pt);border-left:4px solid var(--pc);border-radius:10px;
padding:.35rem .7rem;margin:0 0 .6rem 0;font-size:.9rem;opacity:0;transform:translateY(8px);
animation:stepin .45s ease-out both,hot var(--gap) ease-out both;
animation-delay:calc(var(--i) * var(--gap)),calc(var(--i) * var(--gap));}
.chain .step:last-child{margin-bottom:0;}
.chain .step:not(:last-child)::after{content:"";position:absolute;left:1rem;bottom:-.6rem;height:.6rem;
border-left:3px solid var(--pc);}
.chain.static .step,.chain.static .pbar>span{animation:none;opacity:1;transform:none;}
.chain.static .glow{animation:none;}
.glow{animation:glow 1.3s ease-out both;animation-delay:calc(var(--i) * var(--gap) + .3s);}
.cap{display:inline;color:var(--muted);font-size:var(--small);margin-left:.5rem;}
.step.proof{background:var(--sev1-bg);border-left-color:var(--sev1);}
.step.proof.fail{background:#EEF1F4;border-left-color:#6B7280;}
.step.ask{animation:stepin .45s ease-out both,hot var(--gap) ease-out both,pulse2 1.2s ease-in-out 2;
animation-delay:calc(var(--i) * var(--gap)),calc(var(--i) * var(--gap)),calc(var(--i) * var(--gap) + .4s);}
.chain.static .step.ask{animation:none;}
div[class*="st-key-col-"]{max-height:calc(100vh - 15.5rem);overflow-y:auto;padding-right:.3rem;}
.muted-card{background:#fff;border:1.5px dashed var(--muted);border-radius:var(--radius);padding:.9rem 1.2rem;color:var(--muted);}
/* ---- knowledge base view */
div[class*="st-key-kbtile-"] button{height:auto;min-height:4.1rem;align-items:flex-start;
justify-content:flex-start;text-align:left;white-space:normal;padding:.6rem 1rem;background:#fff;}
div[class*="st-key-kbtile-"] button p{text-align:left;margin:0;font-size:max(15px,.85rem);line-height:1.35;}
div[class*="st-key-kbtile-"] button *{white-space:normal !important;overflow:visible !important;
text-overflow:clip !important;text-align:left !important;}
div[class*="st-key-kbtile-"] button div{justify-content:flex-start !important;}
.kbcard .chip{font-size:max(15px,.66rem);padding:0 .5rem;}
.st-key-stage:has(.kbcard) [data-testid="stVerticalBlock"]{gap:.18rem;}
.st-key-stage:has(.kbcard) .st-key-grow{max-height:calc(100vh - 16rem);overflow-y:auto;}
.st-key-stage:has(.kbcard) .h-big{margin:.1rem 0 0 0;}
.st-key-topbar:has(~ * .kbcard){margin-bottom:.3rem;}
.kbcard .name{font-size:1.2rem;}
.kbcard .chips{gap:.25rem;margin:.1rem 0;}
.kbcard b{font-size:max(15px,.8rem);}
.kbcard .small{font-size:max(15px,.72rem);}
.kbcard ul{margin:0 !important;}
.st-key-stage:has(.kbcard) .h-big{font-size:1.25rem !important;}
div[class*="st-key-kbtile-"] button{padding:.35rem .9rem !important;}
.kbcard li,.kbcard .alert{font-size:max(15px,.68rem) !important;line-height:1.3;}
.kbcard{padding:.3rem 1rem;height:100%;}
.strip{background:var(--accent-soft);border-radius:12px;padding:.3rem 1rem;font-size:max(15px,.85rem);}
.footer{color:var(--muted);font-size:var(--small);text-align:center;margin:.3rem 0 0 0;}
@keyframes fadein{from{opacity:0;transform:translateY(10px);}to{opacity:1;transform:none;}}
@keyframes grow{from{width:0;}}
@keyframes fillbar{from{transform:scaleX(0);}to{transform:scaleX(1);}}
@keyframes stepin{from{opacity:0;transform:translateY(8px);}to{opacity:1;transform:none;}}
@keyframes hot{0%{border-left-width:10px;box-shadow:0 0 0 4px var(--pt);}100%{border-left-width:4px;box-shadow:none;}}
@keyframes glow{0%{box-shadow:0 0 0 0 rgba(15,118,110,.7);}60%{box-shadow:0 0 0 10px rgba(15,118,110,0);}
100%{box-shadow:none;}}
@keyframes pulse2{0%,100%{outline:0 solid rgba(109,40,217,.5);}50%{outline:6px solid rgba(109,40,217,.25);}}
@keyframes pulse{0%,100%{opacity:.8;transform:scale(.97);}50%{opacity:1;transform:scale(1.03);}}
@media (max-height:900px){.st-key-stage:has(.kbcard) .st-key-grow{max-height:calc(100vh - 22.5rem);}}
@media (max-width:1500px){.st-key-view button{font-size:max(15px,.8rem) !important;padding:0 .6rem !important;}.stepsbar .s{padding:.15rem .55rem;}.brand .name{font-size:1.15rem;}.brand .tag{display:none;}}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation:none !important;
transition:none !important;}.chain .step{opacity:1 !important;transform:none !important;}}
</style>
"""
