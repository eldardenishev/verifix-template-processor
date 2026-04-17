from docx.oxml import OxmlElement
from docx.oxml.ns import qn


def make_mergefield(field_name: str) -> OxmlElement:
    """Creates a MERGEFIELD XML element for insertion into a docx paragraph."""
    fld = OxmlElement('w:fldSimple')
    fld.set(qn('w:instr'), f' MERGEFIELD {field_name} \\* MERGEFORMAT ')
    r = OxmlElement('w:r')
    t = OxmlElement('w:t')
    t.text = f'\u00ab{field_name}\u00bb'
    r.append(t)
    fld.append(r)
    return fld


def make_mergefield_with_format(field_name: str, run_element=None) -> OxmlElement:
    """Creates a MERGEFIELD XML element preserving formatting from the original run."""
    fld = OxmlElement('w:fldSimple')
    fld.set(qn('w:instr'), f' MERGEFIELD {field_name} \\* MERGEFORMAT ')

    r = OxmlElement('w:r')

    # Copy run properties (font, size, bold, italic) from original run if available
    if run_element is not None:
        rpr_source = run_element.find(qn('w:rPr'))
        if rpr_source is not None:
            import copy
            rpr_copy = copy.deepcopy(rpr_source)
            r.append(rpr_copy)

    t = OxmlElement('w:t')
    t.text = f'\u00ab{field_name}\u00bb'
    r.append(t)
    fld.append(r)
    return fld
