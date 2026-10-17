import driver, stubs, run_cases, subprocess
run_cases.run(run_cases.extract_cases.cases()[0]) if False else None
print('STUBBED (ledger):', sorted(set(stubs.LEDGER)))
print('NVDA checkout:', subprocess.run(['git','-C',str(driver.boot.R/'nvda-src'),'status','--porcelain'],capture_output=True,text=True).stdout.strip() or 'clean (0 changed files)')
