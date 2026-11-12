import { notFound } from "next/navigation";
import fs from "node:fs";
import path from "node:path";
import { getCircuit, getStatus } from "@/lib/data";
import { CircuitClient } from "@/components/circuit/CircuitClient";

function availableTextLayers(id: string): string[] {
  const dir = path.join(process.cwd(), "public", "data", "text");
  const layers = ["layer1", "layer2", "layer3", "all"];
  return layers.filter((layer) => fs.existsSync(path.join(dir, `${id}.${layer}.txt`)));
}

export default async function CircuitPage({ params }: PageProps<"/circuit/[id]">) {
  const { id } = await params;
  const circuit = getCircuit(id);
  if (!circuit) notFound();

  const status = getStatus();
  const verifierNote =
    status && typeof status.verifier_note === "string"
      ? status.verifier_note
      : "not available";

  return (
    <CircuitClient
      circuit={circuit}
      textDownloads={Object.fromEntries(availableTextLayers(id).map((layer) => [
        layer, `/data/text/${id}.${layer}.txt`,
      ]))}
      verifierNote={verifierNote}
    />
  );
}
