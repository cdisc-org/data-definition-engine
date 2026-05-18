export type ItemGroupDefClassNames =
  | "ADAM OTHER"
  | "BASIC DATA STRUCTURE"
  | "DEVICE LEVEL ANALYSIS DATASET"
  | "EVENTS"
  | "FINDINGS ABOUT"
  | "FINDINGS"
  | "INTERVENTIONS"
  | "MEDICAL DEVICE BASIC DATA STRUCTURE"
  | "MEDICAL DEVICE OCCURRENCE DATA STRUCTURE"
  | "OCCURRENCE DATA STRUCTURE"
  | "REFERENCE DATA STRUCTURE"
  | "RELATIONSHIP"
  | "SPECIAL PURPOSE"
  | "STUDY REFERENCE"
  | "SUBJECT LEVEL ANALYSIS DATASET"
  | "TRIAL DESIGN";

export type ItemGroupDefSubclassNames =
  | "NON-COMPARTMENTAL ANALYSIS"
  | "POPULATION PHARMACOKINETIC ANALYSIS"
  | "TIME-TO-EVENT"
  | "MEDICAL DEVICE TIME-TO-EVENT"
  | "ADVERSE EVENT";

export type ItemGroupDefPurpose = "Tabulation" | "Analysis";

export type PdfPageRefType = "PhysicalRef" | "NamedDestination";

export type Comparator =
  | "LT"
  | "LE"
  | "GT"
  | "GE"
  | "EQ"
  | "NE"
  | "IN"
  | "NOTIN";

export type SoftHard = "Soft" | "Hard";

export type CodeListType = "text" | "float" | "integer";

export type ItemDefDataType =
  | "text"
  | "float"
  | "integer"
  | "date"
  | "datetime"
  | "time"
  | "partialDate"
  | "partialTime"
  | "partialDatetime"
  | "incompleteDatetime"
  | "durationDatetime"
  | "intervalDatetime";

export type OriginType =
  | "Assigned"
  | "Collected"
  | "Derived"
  | "Not Available"
  | "Other"
  | "Predecessor"
  | "Protocol";

export type OriginSource = "Investigator" | "Sponsor" | "Subject" | "Vendor";

export type StandardName =
  | "ADaM-OCCDSIG"
  | "ADaMIG"
  | "ADaMIG-MD"
  | "ADaMIG-NCA"
  | "ADaMIG-popPK"
  | "BIMO"
  | "CDISC/NCI"
  | "SDTMIG"
  | "SDTMIG-AP"
  | "SDTMIG-MD"
  | "SENDIG"
  | "SENDIG-AR"
  | "SENDIG-DART"
  | "SENDIG-GENETOX";
export type StandardType = "CT" | "IG";

export type StandardStatus = "FINAL" | "DRAFT" | "PROVISIONAL" | string;

// Schema for Excel template document
export interface ExcelSchema {
  Study: Study;
  Standards: Standard[];
  Datasets: Dataset[];
  Variables: Variable[];
  ValueLevel: ValueLevel[];
  WhereClauses: WhereClause[];
  CodeLists: CodeList[];
  Dictionaries: Dictionary[];
  Methods: Method[];
  Comments: Comment[];
  Documents: Document[];
}

// Study sheet
export interface Study {
  Attribute:
    | "StudyName"
    | "StudyDescription"
    | "ProtocolName"
    | "Language"
    | "AnnotatedCRF";
  Value: string;
}

// Standard sheet
export interface Standard {
  OID: string;
  Name: StandardName;
  Type: StandardType;
  PublishingSet: string;
  Version: string;
  Status: StandardStatus;
  Comment: string;
}

// Dataset sheet
export interface Dataset {
  OID: string;
  Name: string;
  Description: string;
  Class: ItemGroupDefClassNames;
  Structure: string;
  Purpose: ItemGroupDefPurpose;
  Repeating: "Yes" | "No";
  ReferenceData: "Yes" | "No";
  Comment: string;
  IsNonStandard: "Yes" | "No";
  StandardOID: string;
  HasNoData: "Yes" | "No";
}

// Variable sheet
export interface Variable {
  OID: string;
  Order: number;
  Dataset: string;
  Variable: string;
  Label: string;
  DataType: ItemDefDataType;
  Length: number;
  SignificantDigits: number;
  Format: string;
  KeySequence: number;
  Mandatory: "Yes" | "No";
  CodeList: string;
  ValueList: string;
  OriginType: OriginType;
  OriginSource: OriginSource;
  Pages: string;
  Method: string;
  Predecessor: string;
  Role: string;
  Comment: string;
  IsNonStandard: "Yes" | "No";
  HasNoData: "Yes" | "No";
}

// ValueLevel sheet
export interface ValueLevel extends Variable {
  ItemOID: string;
  WhereClause: string;
}

// WhereClause sheet
export interface WhereClause {
  OID: string;
  Dataset: string;
  Variable: string;
  Comparator: Comparator;
  Value: string;
  Comment: string;
}

// CodeList sheet
export interface CodeList {
  OID: string;
  Name: string;
  NCICodelistCode: string;
  DataType: CodeListType;
  Order: number;
  Term: string;
  NCITermCode: string;
  DecodedValue: string;
  Comment: string;
  IsNonStandard: "Yes" | "No";
  StandardOID: string;
}

// Dictionary sheet
export interface Dictionary {
  OID: string;
  Name: string;
  DataType: CodeListType;
  Dictionary: string;
  Version: string;
}

// Method sheet
export interface Method {
  OID: string;
  Name: string;
  Type: "Computation" | "Imputation";
  Description: string;
  ExpressionContext: string;
  ExpressionCode: string;
  Document: string;
  Pages: string;
}

// Comment sheet
export interface Comment {
  OID: string;
  Description: string;
  Document: string;
  Pages: string;
}

// Document sheet
export interface Document {
  OID: string;
  Title: string;
  Href: string;
}
