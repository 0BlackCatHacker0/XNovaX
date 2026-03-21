import os
P='C:\\ProgramData\\NovaX\\app\\shell\\static\\hivemind.html'
html=open(P,'r',encoding='utf-8').read()

tag='<script src="hivemind_patch.js"></script>'

if tag in html:
    print('ALREADY INJECTED')
elif '</body>' in html:
    html=html.replace('</body>',tag+'\n</body>')
    open(P,'w',encoding='utf-8').write(html)
    print('INJECTED before </body>',len(html),'bytes')
elif '</html>' in html:
    html=html.replace('</html>',tag+'\n</html>')
    open(P,'w',encoding='utf-8').write(html)
    print('INJECTED before </html>',len(html),'bytes')
else:
    html+=tag
    open(P,'w',encoding='utf-8').write(html)
    print('APPENDED',len(html),'bytes')
