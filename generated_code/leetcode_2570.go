package main

import "fmt"

func twoPointers(nums1 [][]int, nums2 [][]int) [][]int {
	n := len(nums1)
	m := len(nums2)
	i, j := 0, 0
	var result [][]int

	for i < n && j < m {
		if nums1[i][0] < nums2[j][0] {
			result = append(result, nums1[i])
			i++
		} else if nums1[i][0] > nums2[j][0] {
			result = append(result, nums2[j])
			j++
		} else {
			nums1[i][1] = nums1[i][1] + nums2[j][1]
			result = append(result, nums1[i])
			i++
			j++
		}
	}

	result = append(result, nums1[i:n]...)
	result = append(result, nums2[j:m]...)
	return result
}

func main() {
	nums1 := [][]int{{1, 2}, {2, 3}, {3, 4}, {5, 6}}
	nums2 := [][]int{{1, 2}, {3, 4}, {4, 2}, {5, 6}}
	res := twoPointers(nums1, nums2)
	fmt.Println(res)
}