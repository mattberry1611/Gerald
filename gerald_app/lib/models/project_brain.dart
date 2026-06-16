class ProjectBrain {
  final String project;
  final String path;
  final String description;
  final String brain;
  final List<String> files;
  final bool hasBrain;

  const ProjectBrain({
    required this.project,
    required this.path,
    required this.description,
    required this.brain,
    required this.files,
    required this.hasBrain,
  });

  factory ProjectBrain.fromJson(Map<String, dynamic> json) {
    return ProjectBrain(
      project: json['project'] as String? ?? '',
      path: json['path'] as String? ?? '',
      description: json['description'] as String? ?? '',
      brain: json['brain'] as String? ?? '',
      files: (json['files'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
      hasBrain: json['has_brain'] as bool? ?? false,
    );
  }

  static ProjectBrain empty(String projectName) => ProjectBrain(
        project: projectName,
        path: '',
        description: '',
        brain: '',
        files: [],
        hasBrain: false,
      );
}
