{{- define "homelab-autodoc.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "homelab-autodoc.fullname" -}}
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

{{- define "homelab-autodoc.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "homelab-autodoc.labels" -}}
helm.sh/chart: {{ include "homelab-autodoc.chart" . }}
{{ include "homelab-autodoc.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "homelab-autodoc.selectorLabels" -}}
app.kubernetes.io/name: {{ include "homelab-autodoc.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "homelab-autodoc.server.fullname" -}}
{{ include "homelab-autodoc.fullname" . }}-server
{{- end -}}

{{- define "homelab-autodoc.server.labels" -}}
{{ include "homelab-autodoc.labels" . }}
app.kubernetes.io/component: server
{{- end -}}

{{- define "homelab-autodoc.server.selectorLabels" -}}
{{ include "homelab-autodoc.selectorLabels" . }}
app.kubernetes.io/component: server
{{- end -}}

{{- define "homelab-autodoc.collector.fullname" -}}
{{ include "homelab-autodoc.fullname" . }}-collector
{{- end -}}

{{- define "homelab-autodoc.collector.labels" -}}
{{ include "homelab-autodoc.labels" . }}
app.kubernetes.io/component: collector
{{- end -}}

{{- define "homelab-autodoc.collector.selectorLabels" -}}
{{ include "homelab-autodoc.selectorLabels" . }}
app.kubernetes.io/component: collector
{{- end -}}

{{- define "homelab-autodoc.server.pushUrl" -}}
{{- if .Values.collector.pushUrl -}}
{{- .Values.collector.pushUrl -}}
{{- else -}}
{{- printf "http://%s.%s.svc.cluster.local:%v" (include "homelab-autodoc.server.fullname" .) .Release.Namespace .Values.server.service.port -}}
{{- end -}}
{{- end -}}
