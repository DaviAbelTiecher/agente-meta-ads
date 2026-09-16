with open('agente.py', 'r', encoding='utf-8', errors='ignore') as f:
    code = f.read()

# Replace modelos_candidatos list
old_block = '''    modelos_candidatos = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-flash-latest"
    ]'''

new_block = '''    modelos_candidatos = [
        "gemini-3.6-flash",
        "gemini-3.7-flash",
        "gemini-3.5-flash",
        "gemini-flash-latest"
    ]'''

if old_block in code:
    code = code.replace(old_block, new_block)
    with open('agente.py', 'w', encoding='utf-8') as f:
        f.write(code)
    print("Successfully replaced modelos_candidatos!")
else:
    print("Could not find exact old_block string.")
