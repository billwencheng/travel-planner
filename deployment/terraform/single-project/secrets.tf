resource "google_secret_manager_secret" "api_keys" {
  secret_id = "${var.project_name}-api-keys"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.services]
}
