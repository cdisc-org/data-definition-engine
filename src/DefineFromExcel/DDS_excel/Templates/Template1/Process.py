from DDS_excel.Templates.Template1.StudySheet import StudySheet
from DDS_excel.Templates.Template1.StandardsSheet import StandardsSheet
from DDS_excel.Templates.Template1.ItemGroups import ItemGroups
from DDS_excel.Templates.Template1.Items import ItemDefs
from DDS_excel.Templates.Template1.WhereClausesSheet import WhereClausesSheet
from DDS_excel.Templates.Template1.CodeListsSheet import CodeListsSheet
from DDS_excel.Templates.Template1.MethodsSheet import MethodsSheet
from DDS_excel.Templates.Template1.DictionariesSheet import DictionariesSheet
from DDS_excel.Templates.Template1.CommentsSheet import CommentsSheet
from DDS_excel.Templates.Template1.DocumentsSheet import DocumentsSheet

#print (DDS_excel.Templates.Template1.WhereClausesSheet.__file__)
def add2Template(template,data):
    for x in data.keys():
        template[x]=data[x]

def process(file,globals,template):
    print ('FILE FROM PROCESS: ',file)
    study = StudySheet(file,globals)._study_template
    add2Template(template,study)

    standards = StandardsSheet(file,globals)._standards_template
    template['standards'] = standards

    datamodel=''
    for x in standards:
        if 'name' in x:
            if x['name'].split('-')[0].endswith('IG') and datamodel != 'ADaMIG':
                datamodel = x['name'].split('-')[0]

    template['itemGroups']  = ItemGroups(file,globals,datamodel)._itemGroups
    template['items'] = ItemDefs(file,globals)._items
    
    conditions = WhereClausesSheet(file,globals)
    template['conditions'] = conditions._conditions
    template['whereClauses'] = conditions._whereclauses

    template['codeLists'] = CodeListsSheet(file,globals)._codelists
    template['methods'] = MethodsSheet(file,globals)._methods
    template['dictionaries'] = DictionariesSheet(file,globals)._dictionaries
    template['comments'] = CommentsSheet(file,globals)._comments
    template['resources'] = DocumentsSheet(file,globals)._documents

    return template