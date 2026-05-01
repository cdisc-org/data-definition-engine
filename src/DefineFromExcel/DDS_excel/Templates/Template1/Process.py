from DDS_excel.Templates.Template1.StudySheet import StudySheet
from DDS_excel.Templates.Template1.StandardsSheet import StandardsSheet
from DDS_excel.Templates.Template1.ItemGroups import ItemGroups
from DDS_excel.Templates.Template1.Items import ItemDefs
from DDS_excel.Templates.Template1.WhereClausesSheet import WhereClausesSheet

#print (DDS_excel.Templates.Template1.WhereClausesSheet.__file__)
def add2Template(template,data):
    for x in data.keys():
        template[x]=data[x]

def process(file,globals,template):

    study = StudySheet(file,globals)._study_template
    add2Template(template,study)

    standards = StandardsSheet(file,globals)._standards_template
    template['standards'] = standards

    datamodel=''
    for x in standards:
        if 'name' in x:
            if x['name'].split('-')[0].endswith('IG'):
                datamodel = x['name'] if x['name'] == 'ADaMIG' else x['name'].split('-')[0]

    itemgroups = ItemGroups(file,globals,datamodel)._itemGroups
    template['itemGroups'] = itemgroups

    itemdefs = ItemDefs(file,globals)._items
    template['items'] = itemdefs

    conditions = WhereClausesSheet(file,globals)
    template['conditions'] = conditions._conditions
    template['whereClauses'] = conditions._whereclauses

    return template