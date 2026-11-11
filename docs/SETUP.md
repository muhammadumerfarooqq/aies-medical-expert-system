# Setup guide (Windows laptop with nothing installed)

1. Install Git: https://git-scm.com/download/win (accept the defaults).
2. Install Python 3.11 or newer from https://www.python.org/downloads/ and tick **"Add python.exe to PATH"**.
3. Open a new PowerShell window and run these commands, one at a time:

```
git clone https://github.com/muhammadumerfarooqq/aies-medical-expert-system.git
cd aies-medical-expert-system
pip install -r requirements.txt
python run_tests.py
```

Expected last line: `TOTAL: 132/132 passed`

4. Try the command-line version:

```
python main.py --symptoms "fever, skin rash, pain behind the eyes" --trace
```

5. Start the graphical app (it opens in your browser):

```
python -m streamlit run app.py
```

Stop it with Ctrl+C in the PowerShell window.

6. If anything fails, take a screenshot of the error and send it to Umer.
