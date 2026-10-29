import { defineRailway, github, postgres, project, service, volume } from "railway/iac";

// Replaces railway.toml (web) and railway.cron.toml (recurring-tasks-cron).
// This is a whole-project file: any resource omitted here can be DELETED on
// `railway config apply`, so Postgres and its volume must stay listed.
export default defineRailway(() => {
  const CHAgent = github("ryanpate/CHAgent", { branch: "main", checkSuites: false });

  // Pin the image the database runs today. Left unset, IaC defaults to
  // postgres:18 — a major upgrade that won't start on the existing v17 volume.
  const Postgres = postgres("Postgres", { region: "us-east4-eqdc4a", image: "ghcr.io/railwayapp-templates/postgres-ssl:17" });
  Postgres.networking = { privateNetworkEndpoint: "postgres", tcpProxies: { "5432": {} } };
  const postgresVolume = volume("postgres-volume", { alerts: { usage: { "100": {}, "80": {}, "95": {} } }, allowOnlineResize: true, region: "us-east4-eqdc4a", sizeMB: 50000 });

  // Daily at 12:00 UTC. Has its own start command and no healthcheck, so it
  // must not inherit the web service's settings.
  const recurringTasksCron = service("recurring-tasks-cron", {
    source: CHAgent,
    // Deploys currently build with nixpacks (set by railway.cron.toml); keep it
    // so cutover doesn't silently switch builders.
    build: { builder: "NIXPACKS" },
    start: "python manage.py create_recurring_tasks && python manage.py send_task_reminders",
    replicas: { "us-east4-eqdc4a": 1 },
    deploy: { cronSchedule: "0 12 * * *", restartPolicyType: "NEVER" },
  });

  const web = service("web", {
    source: CHAgent,
    // Deploys currently build with nixpacks (set by railway.toml).
    build: { builder: "NIXPACKS" },
    // Run migrations at runtime when DATABASE_URL is available.
    start: "python manage.py migrate --noinput && python manage.py create_superuser_from_env && python manage.py create_demo_account && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --timeout 120 --preload --access-logfile - --error-logfile -",
    healthcheck: "/health/",
    healthcheckTimeout: 100,
    replicas: { "us-east4-eqdc4a": 1 },
    deploy: { restartPolicyType: "ON_FAILURE", restartPolicyMaxRetries: 3 },
    // The generated web-production-54cda.up.railway.app domain can't be
    // declared here. The Stripe webhook endpoint still points at it, so check
    // `railway config plan` doesn't remove it — or move the webhook to
    // https://aria.church/webhooks/stripe/ before cutover.
    domains: ["aria.church", "www.aria.church"],
  });

  return project("wonderful-light", {
    variables: { managed: false },
    resources: [Postgres, recurringTasksCron, web, postgresVolume],
  });
});
