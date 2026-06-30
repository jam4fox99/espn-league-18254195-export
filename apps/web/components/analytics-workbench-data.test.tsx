import { describe, expect, it } from "vitest";
import { summaryMetrics } from "@/components/analytics-workbench-data";
import { detailRowsFor } from "@/components/analytics-workbench-details";
import type { AnalyticsData } from "@/lib/product-api";

const analytics: AnalyticsData = {
  modelName: "trade_outcome_v1",
  modelVersion: "mygm-retrospective-v1",
  confidence: "source-backed",
  sourceCoverage: "fixture-free test",
  rows: []
};

describe("analytics workbench source counts", () => {
  it("does not fabricate fixture counts when source rows are unavailable", () => {
    const tradeMetrics = summaryMetrics("trades", analytics, undefined);
    const recordRows = detailRowsFor("records", undefined, analytics.sourceCoverage);

    expect(tradeMetrics.find((metric) => metric.label === "Executed accepts")?.value).toBe(
      "Pending"
    );
    expect(tradeMetrics.find((metric) => metric.label === "Graded trade rows")?.value).toBe(
      "Pending"
    );
    expect(recordRows.find((row) => row.label === "Box score payloads")?.value).toBe("Pending");
    expect(recordRows.find((row) => row.label === "Career seasons included")?.value).toBe(
      "Pending"
    );
    expect(recordRows.find((row) => row.label === "Current score")?.value).toBe("Unavailable");
  });
});
