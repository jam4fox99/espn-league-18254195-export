from mygm_api.analytics_fixtures import PRODUCT_LABEL, analytics_repository
from mygm_api.schemas import AnalyticsCollectionResponse, AnalyticsRowResponse


def analytics_collection(
    version: str,
    model_name: str,
    composite_score: float,
) -> AnalyticsCollectionResponse:
    return AnalyticsCollectionResponse(
        modelName=model_name,
        modelVersion=version,
        confidence="fixture",
        sourceCoverage="local-fixture-contract",
        rows=[
            AnalyticsRowResponse(
                label=PRODUCT_LABEL,
                value=composite_score,
                counts=analytics_repository.metric_counts(model_name),
                caveats=analytics_repository.warnings(version),
            ),
        ],
    )
