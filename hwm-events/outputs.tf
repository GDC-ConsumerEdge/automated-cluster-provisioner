output "function_uri" {
  value = google_cloudfunctions2_function.function.service_config[0].uri
}

output "pubsub_topic_id" {
  value = google_pubsub_topic.topic.id
}

output "firestore_database_name" {
  value = google_firestore_database.database.name
}
