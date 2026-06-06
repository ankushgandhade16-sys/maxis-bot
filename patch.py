import re

with open('test.js', 'r', encoding='utf-8') as f:
    test_js = f.read()

with open('maxis-core/maxis/static/index.html', 'r', encoding='utf-8') as f:
    index_html = f.read()

# 1. Extract ProgrammableMatterEngine from test.js
pm_engine_match = re.search(r'(const pmCanvas.*?)// ═══════════════════════════════════════════════════════════\s*//  8\. ENTITY BODY', test_js, re.DOTALL)
pm_engine_code = pm_engine_match.group(1)

# 2. Extract OrgParticle from test.js
org_particle_match = re.search(r'(class OrgParticle \{.*?\n\})\n\n// Initialize all body parts', test_js, re.DOTALL)
org_particle_code = org_particle_match.group(1)

# 3. Inject ProgrammableMatterEngine before Body config in index.html
if 'ProgrammableMatterEngine' not in index_html:
    index_html = index_html.replace(
        '// ═══════════════════════════════════════════════════════════\n//  8. ENTITY BODY',
        pm_engine_code + '\n// ═══════════════════════════════════════════════════════════\n//  8. ENTITY BODY'
    )

# 4. Replace OrgParticle in index.html
index_html = re.sub(r'class OrgParticle \{.*?\n\}\n\n// Initialize all body parts', org_particle_code + '\n\n// Initialize all body parts', index_html, flags=re.DOTALL)

# 5. Add pmEngine.update(dt) to animate
if 'pmEngine.update(dt)' not in index_html:
    index_html = index_html.replace('brain.tick(dt);', 'brain.tick(dt);\n    pmEngine.update(dt);')

# 6. Add websocket handler for programmable_matter
ws_handler = '''        else if (data.type === 'programmable_matter') {
            pmEngine.setFormation(data.mode, data.data);
            if (data.mode !== 'biological') {
                brain.setBehavior('listening');
            } else {
                brain.setBehavior('floating');
            }
        }'''
if 'programmable_matter' not in index_html:
    index_html = index_html.replace(
        "else if (data.type === 'error')",
        ws_handler + "\n        else if (data.type === 'error')"
    )

with open('maxis-core/maxis/static/index.html', 'w', encoding='utf-8') as f:
    f.write(index_html)

print('Patched successfully!')
