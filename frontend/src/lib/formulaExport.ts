import type { StructuredFormulationView } from "@/types/chat";
import * as XLSX from "xlsx";
import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";

export function formulaToCsv(formulation: StructuredFormulationView): string {
  const header = "ingredient,amount,unit,phase,normalized_name";
  const rows = formulation.ingredients.map((ing) => {
    const amount = ing.amount != null ? String(ing.amount) : "";
    const unit = ing.unit ?? "";
    const phase = ing.phase ?? "";
    const norm = ing.normalized_name ?? "";
    const name = ing.raw_name.replace(/"/g, '""');
    return `"${name}",${amount},"${unit}","${phase}","${norm}"`;
  });
  return [header, ...rows].join("\n");
}

export function formulaToExcelBlob(formulation: StructuredFormulationView): Blob {
  const ingredientRows = formulation.ingredients.map((ing) => ({
    Ingredient: ing.raw_name,
    Amount: ing.amount ?? "",
    Unit: ing.unit ?? "",
    Phase: ing.phase ?? "",
    Normalized: ing.normalized_name ?? "",
  }));
  const procedureRows = (formulation.procedure ?? []).map((step, i) => ({
    Step: i + 1,
    Instruction: step,
  }));
  const metaRows = [
    { Field: "Name", Value: formulation.name },
    { Field: "Formulation ID", Value: formulation.formulation_id },
    { Field: "Document", Value: formulation.doc_id },
    { Field: "Page", Value: formulation.pdf_page },
    { Field: "Confidence", Value: `${(formulation.confidence * 100).toFixed(0)}%` },
    { Field: "Product types", Value: formulation.product_types.join(", ") },
  ];

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(ingredientRows), "Ingredients");
  XLSX.utils.book_append_sheet(
    wb,
    XLSX.utils.json_to_sheet(procedureRows.length ? procedureRows : [{ Step: "", Instruction: "" }]),
    "Procedure",
  );
  XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(metaRows), "Metadata");
  const buffer = XLSX.write(wb, { bookType: "xlsx", type: "array" });
  return new Blob([buffer], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
}

export function formulaToPdfBlob(formulation: StructuredFormulationView): Blob {
  const doc = new jsPDF();
  doc.setFontSize(14);
  doc.text(formulation.name, 14, 18);
  doc.setFontSize(10);
  doc.text(
    `Source: ${formulation.doc_id} · p.${formulation.pdf_page} · ID ${formulation.formulation_id}`,
    14,
    26,
  );

  autoTable(doc, {
    startY: 32,
    head: [["Ingredient", "Amount", "Unit", "Phase"]],
    body: formulation.ingredients.map((ing) => [
      ing.raw_name,
      ing.amount != null ? String(ing.amount) : "—",
      ing.unit ?? "",
      ing.phase ?? "",
    ]),
    styles: { fontSize: 9 },
    headStyles: { fillColor: [124, 74, 220] },
  });

  const finalY = (doc as jsPDF & { lastAutoTable?: { finalY: number } }).lastAutoTable?.finalY ?? 40;
  let y = finalY + 10;
  if ((formulation.procedure ?? []).length > 0) {
    doc.setFontSize(11);
    doc.text("Procedure", 14, y);
    y += 6;
    doc.setFontSize(9);
    for (const step of formulation.procedure ?? []) {
      const lines = doc.splitTextToSize(`• ${step}`, 180);
      doc.text(lines, 14, y);
      y += lines.length * 5;
    }
  }

  return doc.output("blob");
}

export function downloadTextFile(content: string, filename: string, mime: string): void {
  const blob = new Blob([content], { type: mime });
  downloadBlob(blob, filename);
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function safeFormulaFilename(name: string, ext: string): string {
  return `${name.replace(/[^\w.-]+/g, "_").slice(0, 40)}.${ext}`;
}
