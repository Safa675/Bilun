import fs from "node:fs";
import path from "node:path";
import ts from "typescript";
import { describe, expect, it } from "vitest";

// Structural guard complements real mounted streaming tests. Docking must not
// move the panel to a different conditional React tree in either actual page.
describe("page chat mount ownership", () => {
  it.each(["src/app/page.tsx", "src/app/patient/[id]/page.tsx"])("keeps one keyed panel across dock positions in %s", filename => {
    const source = ts.createSourceFile(filename, fs.readFileSync(path.resolve(filename), "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
    const panels: ts.JsxSelfClosingElement[] = [];
    function visit(node: ts.Node) {
      if (ts.isJsxSelfClosingElement(node) && node.tagName.getText(source) === "SutInlineAIPanel") panels.push(node);
      ts.forEachChild(node, visit);
    }
    visit(source);
    expect(panels).toHaveLength(1);
    expect(panels[0].attributes.getText(source)).toContain("key={chatSessionKey}");
    let ancestor: ts.Node | undefined = panels[0].parent;
    while (ancestor && !ts.isReturnStatement(ancestor)) {
      if (ts.isBinaryExpression(ancestor)) expect(ancestor.left.getText(source)).not.toContain("chatDock");
      ancestor = ancestor.parent;
    }
  });
});
