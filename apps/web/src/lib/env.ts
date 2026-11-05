import { z } from "zod";

const schema = z.object({
  API_URL: z.string().url().default("http://localhost:8000"),
});

export function serverEnv() {
  return schema.parse({
    API_URL: process.env.API_URL ?? "http://localhost:8000",
  });
}
