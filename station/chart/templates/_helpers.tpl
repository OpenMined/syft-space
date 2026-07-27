{{/* Base name, overridable. */}}
{{- define "syft-station.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Fully-qualified release name. When the release name already contains the chart
name (the common `helm install syft-station` case) it is used as-is, avoiding a
`syft-station-syft-station` doubling.
*/}}
{{- define "syft-station.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "syft-station.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/* Labels shared by every resource in the release. */}}
{{- define "syft-station.labels" -}}
helm.sh/chart: {{ include "syft-station.chart" . }}
app.kubernetes.io/name: {{ include "syft-station.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
{{- end -}}

{{/*
Per-component selector labels — minimal and immutable (name + instance +
component). Call with a dict: (dict "ctx" . "component" "station").
*/}}
{{- define "syft-station.selectorLabels" -}}
app.kubernetes.io/name: {{ include "syft-station.name" .ctx }}
app.kubernetes.io/instance: {{ .ctx.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{/* The Secret carrying the station's session secret. */}}
{{- define "syft-station.envSecretName" -}}
{{- if .Values.station.existingEnvSecret -}}
{{- .Values.station.existingEnvSecret -}}
{{- else -}}
{{- printf "%s-env" (include "syft-station.fullname" .) -}}
{{- end -}}
{{- end -}}

{{/* docling-serve base URL the station points spaces at. */}}
{{- define "syft-station.doclingUrl" -}}
{{- printf "http://%s:%v" .Values.docling.service.name .Values.docling.service.port -}}
{{- end -}}

{{/*
Public base URL of the station, derived from its own ingress host (the single
source of truth for where it's publicly reachable). Minted into each space
Secret as SYFT_CLUSTER_PUBLIC_URL so buyers reach checkout/balance. Empty when
the ingress is disabled — no public address, so buyer URLs are simply omitted.
*/}}
{{- define "syft-station.publicUrl" -}}
{{- if .Values.station.ingress.enabled -}}
{{- $scheme := ternary "https" "http" .Values.station.ingress.tls.enabled -}}
{{- printf "%s://%s" $scheme .Values.station.ingress.host -}}
{{- end -}}
{{- end -}}
