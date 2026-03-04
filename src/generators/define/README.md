# define_generator.py

## Introduction
The define_generator program takes a Data Definition Specification (DDS) model define-360i.json file as input and 
generates the define.xml file based on that metadata. The DDS model captures the metadata needed to generate a 
Define-XML v2.1 file. The DDS metadata is loaded by another program currently located in the 
[cdisc-org/360i repo](https://github.com/cdisc-org/360i/tree/main/src/define-xml) and generates a Define-XML v2.1 file. The define_generator.py program uses odmlib to 
generate the Define-XML output.

Both this application and create_define_json.py are CLI applications and can be run in sequence to produce a Define-XML 
v2.1 file. Once generated, the Define-XML file can be validated using the Define-XML schema and rendered as HTML using 
the Define-XML style sheet.

The define_generator.py and create_define_json.py are written in Python and are under active development. They are not 
complete, and more features will be added soon. The DDS model is still evolving and will continue to 
change.

## Getting Started
To run define_generator.py from the command-line: 

```Commandline
python define_generator.py -t ./tests/fixtures/define-360i.json -d ./tests/fixtures/define-360i.xml
```

The odmlib package must be installed to run define_generator.py. See the 
[odmlib repository](https://github.com/swhume/odmlib) to install the odmlib source code and latest features. 
The odmlib package can also be installed from PyPi with the understanding that it is still in development 
so might not have everything available in the odmlib repository. It can be installed from PyPi using:

```Commandline
pip install odmlib
```

## Useful Command-line Tools for Working with the Generated Define-XML File
### defineutils Package:

The defineutils package can be installed from PyPi and used to validate and render the Define-XML file as HTML. It can
also be used as a package in your own Python application. Here are some examples of using defineutils from the 
command-line:
```commandline
pip install defineutils
python3 -m defineutils.validate -d define-360i.xml
python3 -m defineutils.definehtml -d define-360i.xml -o define-360i.html
```

### xmllint Command-line Tool:
The xmllint command-line tool can be used to validate the Define-XML file:
```commandline
xmllint --schema ~/src/schemas/DefineV219/schema/cdisc-define-2.1/define2-1-0.xsd ./tests/fixtures/define-360i.xml --noout
```

The xmllint command-line tool can be used to pretty-print the Define-XML file:
```commandline
xmllint --format ./tests/fixtures/define-360i.xml | less
```

## Limitations
define_generator.py is still under development, and the DDS JSON model continues to evolve, so expect changes.
