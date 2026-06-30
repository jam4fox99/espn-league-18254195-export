import { PublicShareReport } from "@/components/public-share-report";

type PublicSharePageProps = {
  readonly params: Promise<{
    readonly shareSlug: string;
  }>;
};

export default async function PublicSharePage({ params }: PublicSharePageProps) {
  const { shareSlug } = await params;
  return <PublicShareReport shareSlug={shareSlug} />;
}
