import { CallDetailView } from "@/components/portal/call-detail-view";

export default async function CallPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <CallDetailView id={id} />;
}
