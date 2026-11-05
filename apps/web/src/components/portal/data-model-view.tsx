const entities = [
  ["clinics", "name, address, hours"],
  ["doctors", "Bangla + English name, specialty"],
  ["services", "duration, BDT fee range"],
  ["patients", "name bn/en, E.164 phone"],
  ["calls", "room, status, summaries"],
  ["transcript_turns", "speaker, text, confidence"],
  ["call_extractions", "intent, confidence, review flag"],
  ["appointments", "doctor + slot, no double book"],
  ["callbacks", "normal or urgent"],
  ["users", "admin or staff"],
];

export function DataModelView() {
  return (
    <div className="space-y-8">
      <section>
        <h1 className="font-display text-3xl text-deep">From the browser to the portal</h1>
        <ol className="mt-4 grid gap-3 md:grid-cols-4">
          {["Browser", "LiveKit", "Nusrat", "FastAPI", "LangGraph", "Postgres", "Portal"].map((step, index) => (
            <li key={step} className="rounded-3xl bg-white p-4 shadow-card">
              <p className="text-xs text-gold">0{index + 1}</p>
              <p className="mt-1 font-semibold">{step}</p>
            </li>
          ))}
        </ol>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-ink/70">
          The browser asks for a token, joins a LiveKit room, and Nusrat talks. Each final turn is posted to the API.
          When the call ends, LangGraph extracts and validates outside the live path, then the portal reads Postgres.
        </p>
      </section>
      <section>
        <h2 className="font-display text-2xl text-deep">Entities</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {entities.map(([name, detail]) => (
            <article key={name} className="rounded-3xl border border-line bg-white p-4">
              <h3 className="font-semibold text-tide">{name}</h3>
              <p className="mt-2 text-sm text-ink/70">{detail}</p>
            </article>
          ))}
        </div>
        <p className="mt-4 text-sm text-ink/70">
          A patient belongs to one clinic. A call may belong to a patient. Turns and one extraction hang off the call.
          An appointment ties patient, doctor, service, and call, and a Postgres exclusion constraint stops two active
          bookings on the same doctor and slot. The full mermaid diagram is in docs/schema.md.
        </p>
      </section>
    </div>
  );
}
