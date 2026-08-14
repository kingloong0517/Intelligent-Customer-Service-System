/**
 * 分类 CRUD API
 */
import request from '../utils/request'

export function getCategories() {
  return request.get('/categories').then((res) => res.data)
}

export function createCategory(name, description) {
  return request
    .post('/categories', { name, description })
    .then((res) => res.data)
}

export function updateCategory(id, name, description) {
  return request
    .put(`/categories/${id}`, { name, description })
    .then((res) => res.data)
}

export function deleteCategory(id) {
  return request.delete(`/categories/${id}`).then((res) => res.data)
}
