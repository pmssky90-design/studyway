from __future__ import annotations

import html
import re
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = next(path for path in ROOT.glob("*.xlsx") if ".backup-" not in path.name)
SHEET = "(학교)고3영어과외"
MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

REPLACEMENTS = {
    "C196": """<h2>청명고등학교 고3영어과외에서 점검한 순서 문항의 연결 근거</h2>
<p>이 고3 학생은 수능형 장문을 읽을 때 각 문장의 해석과 중심 소재를 파악할 수 있었고, 문단의 대략적인 전개도 설명할 수 있었다. 다만 제한시간 안에 순서 문항을 풀면 내용이 자연스럽게 이어지는지를 먼저 생각한 뒤 선택지를 고정하는 경향이 있었다. 문장 사이의 직접 연결 표지는 확인했지만, 그 표지가 가리키는 대상과 앞 문장의 기능까지 함께 대조하지 않아 두 선택지가 비슷해 보이는 순간 판단이 흔들렸다.</p>

<h3>익숙한 소재의 흐름을 먼저 믿은 오답 장면</h3>
<p>한 장문에서는 일반적인 현상을 소개한 뒤 그 설명에 예외가 되는 조건을 제시하고, 마지막에 적용 범위를 다시 제한하는 흐름이 이어졌다. 학생은 첫 부분에서 반복된 소재어를 기준으로 설명 문단 다음에 사례 문단이 올 것이라고 예상했다. 두 선택지 중 하나가 같은 소재어를 여러 번 포함하고 있어 그 선지를 먼저 골랐지만, 실제 연결에는 앞 문장의 복수 대상을 받는 지시어와 제한조건을 이어 주는 역접 표현이 필요했다.</p>
<p>최초 판단에서는 ‘같은 이야기가 이어진다’는 인상을 근거로 삼았다. 그 결과 지시어가 가리키는 대상을 단수로 바꾼 선택지와, 앞에서 제한한 범위를 다시 모든 경우로 넓힌 선택지를 걸러내지 못했다. 문장 해석 자체보다 선지에 들어 있는 소재의 친숙함과 반복 횟수가 판단을 앞선 것이 오답의 직접 원인이었다.</p>

<h3>지시 대상과 제한조건을 따로 회수하기</h3>
<p>청명고등학교고3영어과외에서는 처음 고른 순서를 지운 뒤 각 문장 옆에 두 가지만 기록했다. 먼저 this process, these cases처럼 앞 내용을 받는 표현이 정확히 무엇을 가리키는지 명사 단위로 적었다. 이어 however, only when처럼 방향이나 범위를 바꾸는 표현이 나오면 그 앞뒤에서 유지되는 주장과 새로 제한되는 조건을 분리했다.</p>
<ul>
<li>지시어가 받을 수 있는 선행 대상이 앞 문장에 실제로 존재하는지 확인한다.</li>
<li>사례가 앞의 주장을 뒷받침하는지, 예외를 보여 주는지 기능을 구분한다.</li>
<li>역접 뒤의 제한조건이 다음 문장에서 사라지거나 확대되지 않는지 대조한다.</li>
<li>소재어가 겹친다는 이유만으로 문장 순서를 먼저 고정하지 않는다.</li>
</ul>
<p>재풀이에서는 선택지마다 첫 문장과 마지막 문장만 연결하지 않고, 연결 지점에 필요한 선행 대상과 조건을 짧게 써 보았다. 한 선택지는 같은 소재를 다뤘지만 지시어가 받을 복수 대상이 없었고, 다른 선택지는 제한조건과 사례의 기능이 그대로 이어졌다. 학생은 처음 끌렸던 선지를 유지하는 대신 두 연결 근거가 모두 남는 순서로 판단을 바꿨다.</p>

<h3>표현과 소재를 바꾼 장문에 다시 적용하기</h3>
<p>다음 날에는 이전 표시를 보지 않은 채 소재와 표현이 다른 장문을 제한시간 안에 다시 풀었다. 이번에는 반복되는 단어부터 찾지 않고 각 문단의 마지막 문장에서 주장, 사례, 제한 가운데 어떤 기능이 남는지 먼저 표시했다. 두 선지가 남았을 때도 자연스럽게 읽히는지를 기준으로 고르지 않고, 지시 대상이 실제로 이어지는지와 제한된 범위가 다음 문장에서 유지되는지를 확인했다.</p>
<p>새 지문에서는 사례를 설명하는 문장이 앞 문단과 어휘상 더 가까워 보였지만, 그 위치에는 선행 대상이 없는 지시 표현이 남았다. 학생은 이를 근거로 첫 판단을 보류하고, 앞 문장의 복수 개념과 뒤 문장의 제한조건이 동시에 연결되는 선택지를 남겼다. 청명고등학교 고3영어과외 학습은 정답 번호를 기억하는 방식이 아니라, 소재가 달라져도 지시어와 조건을 회수하는 행동이 유지되는지를 확인하는 것으로 마무리했다.</p>""",
    "C301": """<h2>용인삼계고등학교 고3영어과외에서 다룬 제목 선지의 의미범위</h2>
<p>이 고3 학생은 수능형 장문에서 문단별 핵심 내용을 정리하고 반복되는 개념을 찾을 수 있었다. 그러나 시험 후반에 주제·제목 문항을 만나면 첫 문단에서 눈에 띈 표현을 글 전체의 중심으로 빠르게 확정했다. 뒤 문단의 사례와 결론도 읽었지만, 처음 만든 주제를 수정하기보다 그 주제와 비슷한 단어가 들어간 선지를 남기는 방식으로 판단했다.</p>

<h3>일부 사례를 글 전체의 결론으로 넓힌 순간</h3>
<p>한 장문은 어떤 방식이 유용하게 작동하는 사례를 먼저 보여 준 뒤, 그 효과가 성립하는 조건과 적용할 수 없는 범위를 차례로 설명했다. 학생은 앞부분의 긍정적인 사례를 읽고 ‘해당 방식의 장점’이 글의 제목이라고 판단했다. 선지에서도 장점을 직접 언급한 표현에 먼저 끌렸고, 마지막 문단에 나온 제한과 필자의 최종 판단은 부가 설명으로 처리했다.</p>
<p>하지만 그 선지는 특정 조건에서만 성립하는 효과를 언제나 가능한 결과처럼 넓히고 있었다. 학생은 사례에 등장한 표현이 선지에 그대로 보인다는 이유로 의미범위의 차이를 놓쳤다. 반대로 정답 후보는 원문과 다른 어휘를 사용했지만 장점, 성립조건, 적용 한계를 함께 포함하고 있었다. 최초 판단 오류는 단어의 일치 여부를 글 전체의 주장 범위보다 먼저 확인한 데서 시작됐다.</p>

<h3>사례·조건·결론을 한 문장으로 다시 묶기</h3>
<p>용인삼계고등학교고3영어과외에서는 제목을 고르기 전에 글을 세 부분으로 나눴다. 사례에서는 무엇이 관찰됐는지, 조건에서는 그 결과가 언제 성립하는지, 결론에서는 필자가 어디까지 인정하는지를 각각 한 문장으로 적었다. 이어 세 문장을 하나로 합칠 때 사례의 세부 소재는 줄이고 조건과 결론은 지우지 않았다.</p>
<ul>
<li>첫 문단의 사례가 글 전체 주장인지 설명을 위한 출발점인지 구분한다.</li>
<li>only, unless와 같은 제한 표현이 선지의 의미범위에도 남아 있는지 확인한다.</li>
<li>마지막 문단의 평가가 앞의 장점을 유지하는지, 범위를 축소하는지 표시한다.</li>
<li>원문과 단어가 비슷해도 조건을 삭제한 선지는 제목 후보에서 제외한다.</li>
</ul>
<p>처음 문제를 다시 풀 때 학생은 선택지의 핵심 명사만 비교하지 않고 주체, 주장, 조건을 나란히 적었다. 처음 고른 선지는 주체와 소재는 맞았지만 조건이 빠져 의미가 과장됐다. 다른 선지는 표현이 달랐어도 세 요소를 모두 유지했다. 학생은 마지막 문단의 직접근거를 다시 회수한 뒤 최초 선택을 수정했다.</p>

<h3>새로운 소재와 재진술 선지에서 재적용하기</h3>
<p>다음 날에는 표시와 해설을 보지 않고 소재가 다른 장문과 재진술된 제목 선지를 제한시간 안에 풀었다. 학생은 첫 문단을 읽고 곧바로 제목을 예상하지 않고, 각 문단 끝에 사례·조건·결론 가운데 하나를 적었다. 마지막 문단까지 읽은 뒤에야 세 요소를 포함한 임시 제목을 만들고 선택지와 대조했다.</p>
<p>새 지문에서도 한 선지는 도입부의 구체적인 사례와 어휘가 많이 겹쳤지만, 본문 후반의 예외 조건을 삭제하고 있었다. 학생은 익숙한 표현에 끌린 최초 반응을 그대로 따르지 않고 제한조건이 사라진 위치를 확인했다. 이어 다른 선지가 원문의 단어를 거의 사용하지 않았어도 주장 방향과 적용 범위를 함께 보존한다는 점을 직접근거로 남겼다. 용인삼계고등학교 고3영어과외에서는 소재와 표현이 바뀐 뒤에도 사례를 전체 주장으로 확대하지 않고 결론의 범위를 끝까지 유지하는지를 재확인했다.</p>""",
}


def sheet_path(book: zipfile.ZipFile) -> str:
    workbook = ET.fromstring(book.read("xl/workbook.xml"))
    rels = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
    targets = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels.findall(f"{{{PKG_REL_NS}}}Relationship")}
    for sheet in workbook.find(f"{{{MAIN_NS}}}sheets"):
        if sheet.attrib["name"] == SHEET:
            target = targets[sheet.attrib[f"{{{DOC_REL_NS}}}id"]].lstrip("/")
            return target if target.startswith("xl/") else "xl/" + target
    raise KeyError(SHEET)


def replacement_cell(ref: str, body: str) -> bytes:
    escaped = html.escape(body, quote=False)
    return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escaped}</t></is></c>'.encode("utf-8")


def main() -> None:
    with zipfile.ZipFile(SOURCE, "r") as source_book:
        target = sheet_path(source_book)
        shared_root = ET.fromstring(source_book.read("xl/sharedStrings.xml"))
        shared = ["".join(node.text or "" for node in item.iter() if node.tag.endswith("}t")) for item in shared_root]
        original_xml = source_book.read(target)
        updated_xml = original_xml
        for ref, body in REPLACEMENTS.items():
            pattern = re.compile(rb'<c\s+r="' + ref.encode() + rb'"[^>]*>.*?</c>', re.DOTALL)
            matches = pattern.findall(updated_xml)
            if len(matches) != 1:
                raise RuntimeError(f"{ref}: expected exactly one #ERROR! cell, found {len(matches)}")
            cell = ET.fromstring(matches[0])
            raw = cell.find("v")
            actual = shared[int(raw.text)] if cell.attrib.get("t") == "s" and raw is not None else (raw.text if raw is not None else "")
            if actual != "#ERROR!":
                raise RuntimeError(f"{ref}: expected #ERROR!, found {actual!r}")
            updated_xml = pattern.sub(replacement_cell(ref, body), updated_xml, count=1)
        if updated_xml == original_xml:
            raise RuntimeError("No changes made")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx", dir=ROOT) as handle:
            temp_path = Path(handle.name)
        try:
            with zipfile.ZipFile(temp_path, "w") as output_book:
                for info in source_book.infolist():
                    payload = updated_xml if info.filename == target else source_book.read(info.filename)
                    output_book.writestr(info, payload)
            shutil.move(temp_path, SOURCE)
        finally:
            temp_path.unlink(missing_ok=True)
    print(f"Updated {SHEET}!C196 and {SHEET}!C301 only")


if __name__ == "__main__":
    main()
