{{/*
Expand the name of the chart.
*/}}
{{- define "demo-app.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "demo-app.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "demo-app.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "demo-app.labels" -}}
helm.sh/chart: {{ include "demo-app.chart" . }}
{{ include "demo-app.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "demo-app.selectorLabels" -}}
app.kubernetes.io/name: {{ include "demo-app.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Process environment variables from a list, preserving order
Supports both value and valueFrom objects
Optionally exclude specific names by providing an "exclude" list parameter
Usage: {{- include "demo-app.processEnvsList" (dict "envs" .Values.receiver.env "ctx" .) }}
Usage (with exclusions): {{- include "demo-app.processEnvsList" (dict "envs" .Values.loadgen.env "exclude" (list "TARGET_HOST") "ctx" .) }}
*/}}
{{- define "demo-app.processEnvsList" -}}
{{- $exclude := default list .exclude }}
{{- if .envs }}
{{- range .envs }}
{{- if not (has .name $exclude) }}
- name: {{ .name }}
  {{- if .valueFrom }}
  valueFrom:
    {{- toYaml .valueFrom | nindent 4 }}
  {{- else if .value }}
  value: {{ .value | quote }}
  {{- end }}
{{- end }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Process environment variables from a map, supporting both string values and valueFrom objects
Optionally exclude specific keys by providing an "exclude" list parameter
DEPRECATED: Use processEnvsList for guaranteed order preservation
Usage (all envs): {{- include "demo-app.processEnvs" (dict "envs" .Values.global.envs "ctx" .) }}
Usage (with exclusions): {{- include "demo-app.processEnvs" (dict "envs" .Values.loadgen.env "exclude" (list "TARGET_HOST") "ctx" .) }}
*/}}
{{- define "demo-app.processEnvs" -}}
{{- $exclude := default list .exclude }}
{{- range $key, $value := .envs }}
{{- if not (has $key $exclude) }}
- name: {{ $key }}
  {{- if kindIs "map" $value }}
  {{- if hasKey $value "valueFrom" }}
  valueFrom:
    {{- toYaml $value.valueFrom | nindent 4 }}
  {{- else if hasKey $value "value" }}
  value: {{ $value.value | quote }}
  {{- end }}
  {{- else }}
  value: {{ $value | quote }}
  {{- end }}
{{- end }}
{{- end }}
{{- end }}

