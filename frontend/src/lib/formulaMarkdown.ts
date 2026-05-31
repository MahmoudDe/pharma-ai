import type { StructuredFormulationView } from "@/types/chat";

export function formulaToMarkdown(formulation: StructuredFormulationView): string {
  const lines = [`## ${formulation.name}`, ""];
  if (formulation.product_types.length > 0) {
    lines.push(`**Product types:** ${formulation.product_types.join(", ")}`);
    lines.push("");
  }
  lines.push("| Ingredient | Amount | Phase |");
  lines.push("|------------|--------|-------|");
  for (const ing of formulation.ingredients) {
    const amount =
      ing.amount != null ? `${ing.amount}${ing.unit ?? ""}` : "—";
    lines.push(`| ${ing.raw_name} | ${amount} | ${ing.phase ?? "—"} |`);
  }
  lines.push("");
  lines.push(
    `*Source: ${formulation.doc_id}, PDF p.${formulation.pdf_page}${
      formulation.printed_page != null ? ` · Book p.${formulation.printed_page}` : ""
    }*`,
  );
  return lines.join("\n");
}
