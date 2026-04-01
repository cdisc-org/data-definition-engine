from DDS_excel.Templates.Template1.StudySheet import StudySheet

def add2Template(template,data):
    for x in data.keys():
        template[x]=data[x]

def process(file,globals,template):
    _template = template
    study = StudySheet(file,globals,template)._study_template
    add2Template(_template,study)
    return _template