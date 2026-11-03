// Query name: ModelMetrics
// Requires: ModelParams
//
// A single row, so the measures can reach the intercept and the error bands
// without digging into the raw record.
//
// RMSE matters beyond the metrics card: the API builds the range it returns
// around every estimate as plus or minus one RMSE, so the report's range and
// the product's range come from the same number rather than two opinions.

let
    Metrics = ModelParams[metrics],
    Rows = {[
        mae_dop = Metrics[mae],
        rmse_dop = Metrics[rmse],
        r2 = Metrics[r2],
        intercept_dop = ModelParams[intercept],
        sector_count = List.Count(ModelParams[sectors]),
        feature_count = List.Count(ModelParams[numeric_features])
    ]},
    Typed = Table.FromRecords(
        Rows,
        type table [
            mae_dop = number,
            rmse_dop = number,
            r2 = number,
            intercept_dop = number,
            sector_count = Int64.Type,
            feature_count = Int64.Type
        ]
    )
in
    Typed
