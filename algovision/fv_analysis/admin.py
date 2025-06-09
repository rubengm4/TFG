from django.contrib import admin
from .models import Project, UserProject, File, Algorithm, Execution, Output, FileType

# ModelAdmin para personalizar la vista de administración de Project


class ProjectAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'start_date')
    search_fields = ('title',)
    list_filter = ('start_date',)

# ModelAdmin para personalizar la vista de administración de User


class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'username', 'email', 'joined_date')
    search_fields = ('username', 'email')

# ModelAdmin para personalizar la vista de administración de UserProject


class UserProjectAdmin(admin.ModelAdmin):
    list_display = ('project', 'user', 'role', 'joined_at')
    list_filter = ('role',)

# ModelAdmin para personalizar la vista de administración de File


class FileAdmin(admin.ModelAdmin):
    list_display = ('id', 'type', 'upload_date', 'user')
    list_filter = ('type', 'upload_date', 'user')
    search_fields = ('name',)

# ModelAdmin para personalizar la vista de administración de Algorithm


class AlgorithmAdmin(admin.ModelAdmin):
    readonly_fields = ('archive',)  # file field is read-only
    list_display = ('id', 'name', 'version',
                    'archive', 'project', 'entrypoint')
    search_fields = ('name', 'version', 'project')

# ModelAdmin para personalizar la vista de administración de Execution


class ExecutionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'algorithm', 'status', 'execution_date')
    list_filter = ('status', 'execution_date')
    search_fields = ('user__username', 'algorithm__name', 'status')

# ModelAdmin para personalizar la vista de administración de Report


class OutputAdmin(admin.ModelAdmin):
    list_display = ('id', 'execution', 'output_date', 'file')
    search_fields = ('file',)


class FileTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'code', 'name')
    search_fields = ('code', 'name')


# Registro de los modelos con las clases de administración personalizadas
admin.site.register(Project, ProjectAdmin)
admin.site.register(UserProject, UserProjectAdmin)
admin.site.register(FileType, FileTypeAdmin)
admin.site.register(File, FileAdmin)
admin.site.register(Algorithm, AlgorithmAdmin)
admin.site.register(Execution, ExecutionAdmin)
admin.site.register(Output, OutputAdmin)
