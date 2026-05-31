import type { StructuredFormulationView } from "@/types/chat";

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

export function downloadTextFile(content: string, filename: string, mime: string): void {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
