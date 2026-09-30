#!/usr/bin/env python3
"""Place the tracked NSUT mark on Pandoc's PowerPoint title slide."""

import os
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile, ZipInfo

P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
ET.register_namespace("p", P)
ET.register_namespace("a", A)
ET.register_namespace("r", R)


def child(parent, namespace, tag, **attrs):
    return ET.SubElement(parent, f"{{{namespace}}}{tag}", attrs)


def add_logo(pptx, logo):
    slide_name = "ppt/slides/slide1.xml"
    rel_name = "ppt/slides/_rels/slide1.xml.rels"
    media_name = "ppt/media/nsut-logo.png"
    with ZipFile(pptx) as source:
        if media_name in source.namelist():
            raise ValueError("title logo already present")
        slide = ET.fromstring(source.read(slide_name))
        rels = ET.fromstring(source.read(rel_name))
        tree = slide.find(f"{{{P}}}cSld/{{{P}}}spTree")
        ids = [int(n.get("id")) for n in tree.iter(f"{{{P}}}cNvPr")]
        rel_ids = [int(n.get("Id")[3:]) for n in rels if n.get("Id", "").startswith("rId")]
        rel_id = f"rId{max(rel_ids) + 1}"

        pic = child(tree, P, "pic")
        nv = child(pic, P, "nvPicPr")
        child(nv, P, "cNvPr", id=str(max(ids) + 1), name="NSUT logo")
        child(child(nv, P, "cNvPicPr"), A, "picLocks", noChangeAspect="1")
        child(nv, P, "nvPr")
        fill = child(pic, P, "blipFill")
        child(fill, A, "blip", **{f"{{{R}}}embed": rel_id})
        child(child(fill, A, "stretch"), A, "fillRect")
        shape = child(pic, P, "spPr")
        xfrm = child(shape, A, "xfrm")
        size = 640000  # 0.70 inches, centered above the title
        child(xfrm, A, "off", x=str((9144000 - size) // 2), y="320000")
        child(xfrm, A, "ext", cx=str(size), cy=str(size))
        child(child(shape, A, "prstGeom", prst="rect"), A, "avLst")
        child(rels, REL, "Relationship", Id=rel_id,
              Type=f"{R}/image", Target="../media/nsut-logo.png")

        modified = {
            slide_name: ET.tostring(slide, encoding="utf-8", xml_declaration=True),
            rel_name: ET.tostring(rels, encoding="utf-8", xml_declaration=True),
        }
        fd, temp = tempfile.mkstemp(suffix=".pptx", dir=pptx.parent)
        os.close(fd)
        try:
            with ZipFile(temp, "w") as target:
                for item in source.infolist():
                    target.writestr(item, modified.get(item.filename, source.read(item.filename)))
                info = ZipInfo(media_name, source.getinfo(slide_name).date_time)
                target.writestr(info, logo.read_bytes())
            os.replace(temp, pptx)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)


if __name__ == "__main__":
    add_logo(Path(sys.argv[1]), Path(sys.argv[2]))
