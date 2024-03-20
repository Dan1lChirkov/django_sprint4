from django.http import Http404
from django.urls import reverse, reverse_lazy
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.views.generic import (
    CreateView,
    UpdateView,
    DeleteView,
    ListView
)
from django.db.models.functions import Now
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required

from blog.models import Post, Category, Comment
from .forms import PostForm, CommentForm

User = get_user_model()

MAX_POSTS_IN_ONE_PAGE: int = 10


def get_page_obj(request, posts):
    paginator = Paginator(posts, MAX_POSTS_IN_ONE_PAGE)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return page_obj


def profile(request, username):
    template = 'blog/profile.html'
    profile = get_object_or_404(User, username=username)
    posts = ordered_and_annotated_qs(Post.objects.filter(
        author=profile.id
    ))
    page_obj = get_page_obj(request, posts)
    context = {
        'profile': profile,
        'page_obj': page_obj,
    }
    return render(request, template, context)


def ordered_and_annotated_qs(queryset):
    return queryset.order_by('-pub_date').annotate(comment_count=Count(
        'comments'
    ))


def get_posts_qs():
    is_published: bool = True
    category_is_published: bool = True
    date_time_now = Now()
    return ordered_and_annotated_qs(Post.objects.select_related(
        'author', 'category', 'location'
    ).filter(
        is_published=is_published,
        category__is_published=category_is_published,
        pub_date__lte=date_time_now,
    ))


class PostEditAndDeleteMixin:
    model = Post
    template_name = 'blog/create.html'

    def dispatch(self, request, *args, **kwargs):
        if self.get_object().author != request.user:
            return redirect('blog:post_detail', pk=self.kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)


class CommentEditAndDeleteMixin:
    model = Comment
    template_name = 'blog/comment.html'

    def dispatch(self, request, *args, **kwargs):
        if self.get_object().author != request.user:
            return redirect('blog:post_detail', pk=self.kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)


class PostListView(ListView):
    model = Post
    queryset = get_posts_qs()
    paginate_by = MAX_POSTS_IN_ONE_PAGE
    ordering = '-pub_date'
    template_name = 'blog/index.html'


def post_detail(request, pk):
    template = 'blog/detail.html'
    post = get_object_or_404(
        Post,
        pk=pk)
    comments = post.comments.select_related('author').order_by('created_at')
    form = CommentForm()
    context = {
        'post': post,
        'comments': comments,
        'form': form
    }
    if (
        request.user.username != str(post.author)
        and (not post.is_published or not post.category.is_published)
    ):
        raise Http404('Страница не найдена')
    return render(request, template, context)


def category_posts(request, category_slug):
    template = 'blog/category.html'
    category = get_object_or_404(
        Category,
        is_published=True,
        slug=category_slug)
    posts = get_posts_qs().filter(
        category__slug=category_slug,
    )
    page_obj = get_page_obj(request, posts)
    context = {
        'category': category,
        'page_obj': page_obj,
    }
    return render(request, template, context)


class PostCreateView(LoginRequiredMixin, CreateView):
    model = Post
    template_name = 'blog/create.html'
    form_class = PostForm

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            'blog:profile',
            kwargs={'username': self.request.user.username}
        )


class PostUpdateView(
    LoginRequiredMixin, PostEditAndDeleteMixin, UpdateView
):
    form_class = PostForm

    def get_success_url(self):
        return reverse(
            'blog:post_detail',
            kwargs={'pk': self.kwargs['pk']}
        )


@login_required
def add_commnet(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.author = request.user
        comment.post = post
        comment.save()
    return redirect('blog:post_detail', pk=post_id)


class CommentEditView(
    LoginRequiredMixin, CommentEditAndDeleteMixin, UpdateView
):
    form_class = CommentForm

    def get_success_url(self):
        return reverse(
            'blog:post_detail',
            kwargs={'pk': self.kwargs['pk']}
        )


class CommentDeleteView(
    LoginRequiredMixin, CommentEditAndDeleteMixin, DeleteView
):

    def get_success_url(self):
        return reverse_lazy(
            'blog:profile',
            kwargs={'username': self.request.user}
        )


class PostDeleteView(
    LoginRequiredMixin, PostEditAndDeleteMixin, DeleteView
):

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = PostForm(instance=self.object)
        return context

    def get_success_url(self):
        return reverse(
            'blog:profile',
            kwargs={'username': self.request.user}
        )


class EditProfileView(LoginRequiredMixin, UpdateView):
    model = User
    template_name = 'blog/user.html'
    fields = ['first_name', 'last_name', 'username', 'email']

    def get_object(self, queryset=None):
        return self.request.user

    def get_success_url(self):
        return reverse(
            'blog:profile',
            kwargs={'username': self.request.user.username}
        )
