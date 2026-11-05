import { PatientDetailView } from "@/components/portal/records-view";

export default async function PatientPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <PatientDetailView id={id} />;
}
