import re, sys, zipfile, shutil
src,dst=sys.argv[1],sys.argv[2]
z=zipfile.ZipFile(src); doc=z.read('word/document.xml').decode('utf-8')
SP='<w:r><w:t xml:space="preserve"> </w:t></w:r>'
def merge_cell(m):
    tc=m.group(0)
    paras=re.findall(r'<w:p\b.*?</w:p>',tc,re.S)
    if len(paras)<2: return tc
    runs=[]
    for p in paras:
        body=re.sub(r'^<w:p\b[^>]*>(?:<w:pPr>.*?</w:pPr>)?','',p,flags=re.S)[:-len('</w:p>')]
        body=re.sub(r'<w:br/>',' ',body)
        if re.search(r'<w:t|<w:drawing',body): runs.append(body)
    first=paras[0]
    head=re.match(r'^<w:p\b[^>]*>(?:<w:pPr>.*?</w:pPr>)?',first,re.S).group(0)
    newp=head+SP.join(runs)+'</w:p>'
    start=tc.index(paras[0]); end=tc.rindex(paras[-1])+len(paras[-1])
    return tc[:start]+newp+tc[end:]
doc=re.sub(r'<w:tc>.*?</w:tc>',merge_cell,doc,flags=re.S)
with zipfile.ZipFile(dst,'w',zipfile.ZIP_DEFLATED) as out:
    for it in z.infolist():
        out.writestr(it, doc.encode('utf-8') if it.filename=='word/document.xml' else z.read(it.filename))
