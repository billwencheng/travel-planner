resource "google_secret_manager_secret" "api_keys" {
  for_each  = local.deploy_project_ids
  secret_id = "${var.project_name}-api-keys"
  project   = each.value

  replication {
    auto {}
  }

  depends_on = [google_project_service.deploy_project_services]
}
