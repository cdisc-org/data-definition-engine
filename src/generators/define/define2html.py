import argparse
from lxml import etree

def transform_xml(xml_path, xsl_path, output_path):
    """
    Transforms an XML file using an XSLT stylesheet.
    Args:
        xml_path (str): Path to the XML file.
        xsl_path (str): Path to the XSLT stylesheet file.
        output_path (str, optional): Path to save the transformed HTML file.
    """
    xml_tree = etree.parse(xml_path)
    xsl_tree = etree.parse(xsl_path)
    transform = etree.XSLT(xsl_tree)
    result_tree = transform(xml_tree)

    if output_path:
        with open(output_path, 'wb') as f:
            f.write(etree.tostring(result_tree, pretty_print=True))
    else:
        print(etree.tostring(result_tree, pretty_print=True).decode())

def set_cmd_line_args():
    """
    get the command-line arguments needed to convert the define.xml input a define.html file
    :return: return the argparse template with the command-line parameters
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--define", help="path and file name of Define-XML v2 file to create", required=True,
                        dest="define_file", default="./fixtures/define-360i.xml")
    parser.add_argument("-s", "--stylesheet", help="path and file name of the Define-XML style sheet", required=True,
                        dest="style_sheet", )
    parser.add_argument("-o", "--output", help="path and file name of Define-XML HTML output", required=False,
                        dest="output_file", default="./fixtures/define-360i.html")
    parser.add_argument("-v", "--verbose", help="turn on verbose processing", default=False, const=True,
                        nargs='?', dest="is_verbose")
    args = parser.parse_args()
    return args


def main():
    args = set_cmd_line_args()
    transform_xml(args.define_file, args.style_sheet, args.output_file)

if __name__ == "__main__":
    main()
