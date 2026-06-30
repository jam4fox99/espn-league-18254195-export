import { AppFrame } from "@/components/app-frame";
import { AuthGate } from "@/components/auth-gate";
import { ClientOnly } from "@/components/client-only";
import { LeagueNewsPage } from "@/components/league-news-page";

type NewsPageProps = {
  readonly params: Promise<{
    readonly leagueId: string;
  }>;
};

export default async function NewsPage({ params }: NewsPageProps) {
  const { leagueId } = await params;
  return (
    <AppFrame>
      <ClientOnly>
        <AuthGate>
          <LeagueNewsPage leagueId={leagueId} />
        </AuthGate>
      </ClientOnly>
    </AppFrame>
  );
}
