from django.contrib import admin

from .forms import AlgorithmArchiveWidget
from .models import Project, UserProject, File, Algorithm, Execution, Output, FileType

# ModelAdmin to customize the admin view of Project


class ProjectAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'start_date')
    search_fields = ('title',)
    list_filter = ('start_date',)

# ModelAdmin to customize the admin view of User (Django's built-in User model is not registered here, but if you have a custom user model, you can register it similarly)


class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'username', 'email', 'joined_date')
    search_fields = ('username', 'email')

# ModelAdmin to customize the admin view of UserProject


class UserProjectAdmin(admin.ModelAdmin):
    list_display = ('project', 'user', 'joined_at')
    list_filter = ('project', 'user')
    search_fields = ('project__title', 'user__username')

# ModelAdmin to customize the admin view of File, showing the file type and allowing filtering by type and upload date


class FileAdmin(admin.ModelAdmin):
    list_display = ('id', 'display_name', 'type', 'upload_date', 'user')
    list_filter = ('type', 'upload_date', 'user')
    search_fields = ('display_name',)

# ModelAdmin to customize the admin view of Algorithm, showing the project it belongs to and allowing filtering by project and version


class AlgorithmAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'version',
                    'archive', 'project', 'entrypoint')
    search_fields = ('name', 'version', 'project')

    def save_model(self, request, obj, form, change):
        if not change:
            uploaded = form.cleaned_data.get("archive")
            obj.archive = None
            super().save_model(request, obj, form, change)
            if uploaded:
                obj.archive.save(uploaded.name, uploaded, save=True)
        else:
            super().save_model(request, obj, form, change)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "archive":
            kwargs["widget"] = AlgorithmArchiveWidget(attrs={"accept": ".zip"})
        return super().formfield_for_dbfield(db_field, request, **kwargs)

# ModelAdmin to customize the admin view of Execution, showing the user, algorithm, status, execution date, and allowing filtering by status and execution date. Also show the name of the snapshot file if it exists.


class ExecutionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'algorithm', 'status',
                    'execution_date', 'snapshot_file_name')
    list_filter = ('status', 'execution_date')
    search_fields = ('user__username', 'algorithm__name', 'status')

# ModelAdmin to customize the admin view of Output, showing the execution it belongs to, the output date, and allowing filtering by execution and output date. Also show the name of the output file if it exists.


class OutputAdmin(admin.ModelAdmin):
    list_display = ('id', 'execution', 'output_date', 'file')
    search_fields = ('file',)

# ModelAdmin to customize the admin view of FileType, showing the code and name, and allowing searching by code and name


class FileTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'code', 'name')
    search_fields = ('code', 'name')


# Registering the models with their respective custom ModelAdmin classes
admin.site.register(Project, ProjectAdmin)
admin.site.register(UserProject, UserProjectAdmin)
admin.site.register(FileType, FileTypeAdmin)
admin.site.register(File, FileAdmin)
admin.site.register(Algorithm, AlgorithmAdmin)
admin.site.register(Execution, ExecutionAdmin)
admin.site.register(Output, OutputAdmin)
