resource "google_firestore_database" "databases" {
  for_each    = local.deploy_project_ids
  project     = each.value
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"
  depends_on  = [google_project_service.deploy_project_services]
}
