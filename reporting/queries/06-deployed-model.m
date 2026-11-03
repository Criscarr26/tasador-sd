// Query name: DeployedModel
// Requires: ModelParams
//
// Is this report showing the model that is actually live?
//
// The file on disk can fall behind production, or production behind the file,
// and either way the report keeps drawing confident numbers from whichever it
// has. This query asks the API and puts the answer on the page, so a stale
// report announces itself.
//
// Public endpoints, no credentials. Delete this query if you want the report
// to open with no network access at all.

let
    ApiUrl = "https://tasador-sd.vercel.app",
    Health = Json.Document(Web.Contents(ApiUrl & "/health")),
    Deployed = Json.Document(Web.Contents(ApiUrl & "/v1/model/params")),
    Rows = {[
        health_status = Health[status],
        deployed_version = Deployed[version],
        deployed_intercept = Deployed[params][intercept],
        local_intercept = ModelParams[intercept],
        // Both sides are the same float written by the same JSON encoder, so
        // an exact comparison is the right one and a tolerance would only
        // hide a real mismatch.
        matches_local = Deployed[params][intercept] = ModelParams[intercept]
    ]},
    Typed = Table.FromRecords(
        Rows,
        type table [
            health_status = text,
            deployed_version = text,
            deployed_intercept = number,
            local_intercept = number,
            matches_local = logical
        ]
    )
in
    Typed
